import json
import os
import re
import subprocess
import threading
import urllib.error
from collections import deque
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agent import (
    EMPTY_PATCH,
    apply_agent_patch,
    fallback_answer,
    finish_ask,
    is_gage_id,
    is_safe_output_dir,
    note_for_ask,
    read_named_coordinates,
    sanitize_agent_patch,
    with_hourly_clocks,
)
from .datastream_command import chosen_warmup_days, datastream_command
from .forcings import FORCINGS
from .hydrograph import hydrograph as build_hydrograph
from .nearest_gages import bounds_for_gages, lookup_nearest_gages
from .nextgen_gages import nextgen_gage_ids
from .nlp import agent_system_prompt, interpret_evaluate
from .parse_request import read_warmup_days
from .review import review_plan
from .place_query import place_query_from_sentence
from .plan import build_plan, plan_coordinates
from .realizations import (
    DEFAULT_REALIZATION,
    REALIZATIONS,
    live_log_path_for,
    log_path_for,
    output_dir_for,
    result_path_for,
)
from .repair_watershed_ids import repair_watershed_ids
from .site_name import choose_place_hit, lookup_station_name, lookup_station_point, search_places
from .watershed import resolve_watershed_geopackage, watershed_geopackage
from .watershed_geojson import watershed_geojson

from .settings import DATASTREAM_ROOT, NGIAB_PREP_PYTHON, OPENAI_MODEL, ROOT
from .run_check import problems_text, run_problems
from .setup_check import explain_failure, setup_problems

WEB = ROOT / "web"
SCRIPT = DATASTREAM_ROOT / "scripts" / "datastream"
KEY_FILES = [ROOT / ".openai-key.local", ROOT.parent / "NextGenHydro" / ".openai-key.local"]
WATERSHED_ROOT = Path.home() / "ngiab_preprocess_output"
LOG_TAIL = 80_000

RUNNING: subprocess.Popen | None = None
WATERSHED_BUSY = False
WATERSHED_BUILD: dict | None = None
LOCK = threading.Lock()


def api_key() -> str:
    for path in KEY_FILES:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        if text and not re.search(r"\s", text):
            return text
    env = os.environ.get("OPENAI_API_KEY", "").strip()
    if env and not re.search(r"\s", env):
        return env
    return ""


def clean_api_key(value) -> str:
    if not isinstance(value, str):
        return ""
    key = value.strip()
    if not key or len(key) > 400 or re.search(r"\s", key):
        return ""
    return key


def _parse_json_object(text: str):
    trimmed = text.strip()
    if not trimmed:
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", trimmed)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _extract_json(payload: dict):
    for item in payload.get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") == "output_json" and part.get("json") is not None:
                return part["json"]
    chunks = []
    for item in payload.get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    joined = _parse_json_object("".join(chunks))
    if joined is not None:
        return joined
    if isinstance(payload.get("output_text"), str):
        return _parse_json_object(payload["output_text"])
    return None


CHECK_TOOLS = [
    {
        "type": "function",
        "name": "check_gauge",
        "description": "Ask whether the USGS gauge digits from the sentence are in the NextGen hydrofabric.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"gage": {"type": "string", "description": "Gauge digits from the sentence, or an empty string."}},
            "required": ["gage"],
        },
    },
    {
        "type": "function",
        "name": "check_coordinates",
        "description": "Ask whether the sentence latitude and longitude are inside the valid ranges.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "lat": {"type": ["number", "null"]},
                "lng": {"type": ["number", "null"]},
            },
            "required": ["lat", "lng"],
        },
    },
    {
        "type": "function",
        "name": "check_dates",
        "description": "Ask whether the start is before the end, and whether a forecast window has already ended.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "type": "function",
        "name": "check_models",
        "description": "Pass the catalog model the sentence means after you have read it. Noah means Noah-OWP-Modular. Rust and LSTM together mean the one model LSTM Rust. Do not pass a fragment such as rust as its own model. A request for routing or a compatible routing configuration means t-route, so pass t-route. A compatible PET formulation means PET, so pass PET. without, not using, and do not use exclude that model, so do not pass an excluded model. This function searches the DataStreamCLI list and says which resolved names are not supported. Pass an empty list when the sentence names no model.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hydrologic model names read from the sentence.",
                }
            },
            "required": ["models"],
        },
    },
]


def _post_openai(key: str, payload: dict) -> dict | None:
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        print(f"OpenAI request failed ({error.code}): {detail}")
        return None
    except Exception as error:
        print(f"OpenAI request failed: {error}")
        return None


def _function_calls(payload: dict) -> list[dict]:
    calls = []
    for item in payload.get("output") or []:
        if item.get("type") == "function_call" and item.get("name") in {"check_gauge", "check_coordinates", "check_dates", "check_models"}:
            calls.append(item)
    return calls


def _tool_arguments(call: dict) -> dict:
    raw = call.get("arguments") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _plan_schema() -> dict:
    return {
        "type": "json_schema",
        "name": "nextgen_form",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "gage": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "forcing": {"type": "string", "enum": ["", *[item["id"] for item in FORCINGS]]},
                "realization": {"type": "string", "enum": ["", *[item["id"] for item in REALIZATIONS]]},
                "lat": {"type": ["number", "null"]},
                "lng": {"type": ["number", "null"]},
                "outputDir": {"type": "string"},
                "location": {"type": "string"},
                "action": {"type": "string", "enum": ["", "run", "dry run", "do not run"]},
                "logging": {"type": "string", "enum": ["", "verbose"]},
                "nprocs": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 256,
                    "description": "Process cap for NextGen and forcingprocessor. Same as -n / --NPROCS. Read the sentence for a request to parallelize or to limit cores, CPUs, workers, or processes. Default 4.",
                },
                "note": {"type": "string"},
                "models": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["gage", "start", "end", "forcing", "realization", "lat", "lng", "outputDir", "location", "action", "logging", "nprocs", "note", "models"],
        },
    }


def _reviewed_from_calls(sentence: str, calls: list[dict]) -> dict:
    draft: dict = {}
    for call in calls:
        for key, value in _tool_arguments(call).items():
            if value not in ("", None):
                draft[key] = value
    return review_plan(sentence, draft)


def _ask_with_checks(key: str, sentence: str) -> dict | None:
    opened = _post_openai(
        key,
        {
            "model": OPENAI_MODEL,
            "input": [
                {
                    "role": "system",
                    "content": "Read the sentence for its meaning, then call check_gauge, check_coordinates, check_dates, and check_models. Resolve model words before you pass them. Noah means Noah-OWP-Modular. Rust and LSTM together are the one model LSTM Rust, so pass LSTM Rust and do not pass rust by itself. A request for routing or a compatible routing configuration means t-route, so pass t-route. A compatible PET formulation means PET. without, not using, and do not use exclude that model. An empty models list means the sentence named no model. check_dates also says whether a forecast window has already ended. When it says the dates are already in the past, write that in the note later and set action to do not run. Do not choose the realization file in this step. Do not write the plan yet.",
                },
                {"role": "user", "content": sentence},
            ],
            "tools": CHECK_TOOLS,
            "tool_choice": "required",
            "max_output_tokens": 2000,
            "reasoning": {"effort": "low"},
        },
    )
    if not opened:
        return None
    calls = _function_calls(opened)
    reviewed = _reviewed_from_calls(sentence, calls)
    if not calls:
        return {"reviewed": reviewed, "json": None}
    follow = _post_openai(
        key,
        {
            "model": OPENAI_MODEL,
            "previous_response_id": opened.get("id"),
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": json.dumps(reviewed["checks"].get(call.get("name"), {})),
                }
                for call in calls
                if call.get("call_id")
            ]
            + [
                {
                    "role": "system",
                    "content": agent_system_prompt(),
                }
            ],
            "text": {"format": _plan_schema()},
            "max_output_tokens": 2000,
            "reasoning": {"effort": "low"},
        },
    )
    return {"reviewed": reviewed, "json": _extract_json(follow) if follow else None}


def call_openai(key: str, sentence: str, form: dict, schema_mode: bool) -> dict:
    prompt = agent_system_prompt()
    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": prompt if schema_mode else f"{prompt} Return only a single JSON object."},
            {"role": "user", "content": json.dumps({"sentence": sentence, "currentForm": form})},
        ],
        "max_output_tokens": 2000,
        "reasoning": {"effort": "low"},
    }
    if schema_mode:
        payload["text"] = {"format": _plan_schema()}
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        return {"reached": True, "json": _extract_json(body)}
    except Exception:
        return {"reached": False, "json": None}


def ask_sentence(sentence: str, _form: dict | None = None) -> dict:
    key = api_key()
    answer = None
    if key:
        current = {
            "gage": "",
            "start": "",
            "end": "",
            "forcing": "",
            "realization": "",
            "lat": None,
            "lng": None,
            "outputDir": "",
        }
        checked = _ask_with_checks(key, sentence)
        raw = checked["json"] if checked else None
        if raw is None:
            first = call_openai(key, sentence, current, True)
            raw = first["json"]
            if first["reached"] and raw is None:
                raw = call_openai(key, sentence, current, False)["json"]
        if raw is not None:
            patch = with_hourly_clocks(sanitize_agent_patch(raw))
            named_models = raw.get("models") if isinstance(raw.get("models"), list) else []
            if not named_models and checked and checked.get("reviewed"):
                named_models = checked["reviewed"].get("askedModels") or []
            patch["models"] = named_models
            note = patch.get("note") or ""
            answer = finish_ask({"patch": {**patch, "note": note}, "note": note, "usedModel": True}, sentence)
        elif checked and checked.get("reviewed"):
            patch = checked["reviewed"]["patch"]
            note = " ".join(checked["reviewed"]["messages"])
            answer = finish_ask({"patch": {**patch, "note": note}, "note": note, "usedModel": True}, sentence)
    if answer is None:
        answer = finish_ask(fallback_answer(sentence), sentence)
    current_form = {
        "request": {"gage": "", "start": "", "end": "", "forcing": ""},
        "runOptions": {"outputDir": "", "realization": DEFAULT_REALIZATION},
        "outlet": None,
    }
    merged = apply_agent_patch(current_form, answer["patch"])
    named = read_named_coordinates(sentence)
    gage_named = re.search(r"\b\d{7,15}\b", sentence) is not None
    place = answer["patch"].get("location", "").strip()
    gages = []
    if named and not named["valid"]:
        hunt = False
        focus = None
        message = answer.get("note", "")
    elif named and named["valid"] and not gage_named:
        hunt = False
        focus = {"lng": named["lng"], "lat": named["lat"], "zoom": 12}
        gages = answer.get("gages") or lookup_nearest_gages(focus, nextgen_gage_ids)
        message = note_for_ask(answer, merged["request"])
        if gages and not answer["patch"].get("gage"):
            nearest = gages[0]
            answer["patch"]["gage"] = nearest["id"]
            answer["patch"]["location"] = nearest.get("name") or ""
            merged["request"]["gage"] = nearest["id"]
            merged["outlet"] = {"lat": named["lat"], "lng": named["lng"]}
        if gages:
            focus = _focus_on_gages(gages) or focus
            if "nearest NextGen gauge" not in message:
                message = f"{message} The nearest NextGen gauge is USGS {gages[0]['id']}."
        elif not gages:
            answer["patch"]["action"] = "do not run"
            if "No NextGen gauge was found" not in message:
                message = f"{message} No NextGen gauge was found at that point, so the gauge number stays empty and this run is not ready."
    else:
        point_named = answer["patch"].get("lat") is not None and answer["patch"].get("lng") is not None
        hunt = not gage_named and (place != "" or point_named)
        if hunt:
            merged["request"]["gage"] = ""
        focus = _focus(sentence, "" if hunt else merged["request"]["gage"], answer["patch"], place)
        message = note_for_ask(answer, merged["request"])
        if hunt and focus:
            gages = lookup_nearest_gages(focus, nextgen_gage_ids)
            if gages:
                message = f"{message} The nearest NextGen stations are on the map. Pick one to fill the gauge in the plan."
                focus = _focus_on_gages(gages) or focus
            else:
                message = f"{message} No NextGen station was found near that place. The gauge stays empty."
        elif hunt and not focus:
            message = f"{message} That place was not found, so no gauges were marked. The gauge stays empty."
    points = plan_coordinates(sentence, merged["request"].get("gage") or "")
    plan = build_plan(
        answer["patch"].get("location", ""),
        merged["request"],
        merged["runOptions"]["realization"],
        merged["runOptions"]["outputDir"],
        bool(answer["patch"].get("realization")),
        answer["patch"].get("action", ""),
        answer["patch"].get("logging", ""),
        answer["patch"].get("nprocs", 4),
        message,
        points["gauge_latitude"],
        points["gauge_longitude"],
        points["outlet_latitude"],
        points["outlet_longitude"],
    )
    named_warmup = read_warmup_days(sentence)
    plan["warmupDays"] = chosen_warmup_days(named_warmup, plan.get("forcing") or "", plan.get("start") or "", plan.get("end") or "")
    plan["evaluate"] = interpret_evaluate(sentence)
    if plan["warmupDays"] and f"{plan['warmupDays']} warm-up days" not in plan.get("note", ""):
        reason = "because the sentence asked for it" if named_warmup else "so soil and groundwater storage can settle before the dates you asked for"
        plan["note"] = f"{plan.get('note', '')} The run adds {plan['warmupDays']} warm-up days before the start {reason}.".strip()
    if plan["evaluate"]:
        plan["note"] = f"{plan.get('note', '')} TEEHR evaluation against USGS observations is on.".strip()
    return {
        "usedModel": answer["usedModel"],
        "note": message.strip(),
        "patch": answer["patch"],
        "request": merged["request"],
        "runOptions": merged["runOptions"],
        "outlet": merged["outlet"],
        "plan": plan,
        "hunt": hunt,
        "gages": [{**gage, "miles": round(gage["miles"], 1)} for gage in gages],
        "focus": focus,
        "forcings": FORCINGS,
        "realizations": REALIZATIONS,
    }


def _focus_on_gages(gages: list[dict]) -> dict | None:
    box = bounds_for_gages(gages)
    if not box:
        return None
    return {"bounds": box}


def _focus(sentence: str, gage: str, patch: dict, place_name: str) -> dict | None:
    named = read_named_coordinates(sentence)
    if named and named.get("valid"):
        return {"lng": named["lng"], "lat": named["lat"], "zoom": 12}
    if patch.get("lat") is not None and patch.get("lng") is not None:
        return {"lng": patch["lng"], "lat": patch["lat"], "zoom": 12}
    if is_gage_id(gage):
        site = lookup_station_point(gage)
        if site:
            return {"lng": site["lng"], "lat": site["lat"], "zoom": 11}
    names = []
    if place_name.strip():
        names.append(place_name.strip())
    parsed = place_query_from_sentence(sentence) or ""
    if parsed and parsed not in names:
        names.append(parsed)
    for place in names:
        hit = choose_place_hit(place, search_places(place))
        if hit:
            return {"lng": hit["lng"], "lat": hit["lat"], "zoom": hit["zoom"]}
    return None


def check_run(body: dict) -> dict:
    problems = run_problems(body)
    command = None
    status = 400
    if not any(item["field"] in {"gage", "start", "end", "output"} for item in problems):
        command = datastream_command(
            {"gage": body.get("gage") or "", "start": body.get("start") or "", "end": body.get("end") or "", "forcing": body.get("forcing") or ""},
            {"outputDir": body.get("outputDir") or "", "realization": body.get("realization") or "", "action": body.get("action") or "", "logging": body.get("logging") or "", "nprocs": body.get("nprocs", 4), "warmupDays": body.get("warmupDays"), "evaluate": body.get("evaluate")},
        )
    if not problems:
        if not SCRIPT.exists():
            problems.append({"field": "", "message": f"DataStreamCLI was not found at {DATASTREAM_ROOT}. Set DATASTREAM_ROOT and restart the app."})
            status = 500
        else:
            root = output_root(body.get("gage") or "", body.get("outputDir") or "")
            if root and root.exists():
                problems.append({"field": "output", "message": f"The output folder {output_dir_for('', body.get('outputDir') or '')} already exists. Type a new folder name."})
                status = 409
    return {"problems": problems, "command": command, "status": status}


def output_root(gage: str, output_dir: str) -> Path | None:
    if not is_gage_id(gage) or not is_safe_output_dir(output_dir) or len(output_dir) > 500:
        return None
    if ".." in re.split(r"[/\\]", output_dir):
        return None
    folder = output_dir_for(gage, output_dir)
    if not folder or ".." in re.split(r"[/\\]", folder):
        return None
    return (DATASTREAM_ROOT / folder).resolve()


def read_tail(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError:
        return {"text": "", "exists": False, "truncated": False}
    length = min(size, LOG_TAIL)
    with path.open("rb") as handle:
        handle.seek(max(0, size - length))
        text = handle.read().decode("utf-8", "replace")
    return {"text": text, "exists": True, "truncated": size > LOG_TAIL}


def list_result_files(directory: Path) -> list[dict]:
    out = []

    def walk(current: Path, depth: int) -> None:
        if len(out) >= 200 or depth > 2 or not current.is_dir():
            return
        for entry in sorted(current.iterdir(), key=lambda item: item.name):
            if len(out) >= 200 or entry.name.startswith("."):
                continue
            if entry.is_dir():
                walk(entry, depth + 1)
            elif entry.is_file():
                out.append({"name": entry.relative_to(directory).as_posix(), "bytes": entry.stat().st_size})

    walk(directory, 0)
    return out


def _write_both(chunks: list[str], handler, text: str) -> None:
    data = text.encode("utf-8")
    chunks.append(text)
    try:
        handler.wfile.write(data)
        handler.wfile.flush()
    except Exception:
        pass


def ensure_watershed(gage: str, write) -> bool:
    global RUNNING, WATERSHED_BUSY
    gpkg = Path(resolve_watershed_geopackage(gage, str(Path.home())))
    if not gpkg.exists():
        write(f"Building the watershed for USGS {gage} with NGIAB Data Preprocess.\n")
        (Path.home() / ".ngiab").mkdir(parents=True, exist_ok=True)
        WATERSHED_ROOT.mkdir(parents=True, exist_ok=True)
        child = subprocess.Popen(
            ["uvx", "--python", NGIAB_PREP_PYTHON, "ngiab-prep", "--output_root", str(WATERSHED_ROOT), "-i", f"gage-{gage}", "-s"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        RUNNING = child
        if child.stdin:
            child.stdin.write(b"y\n" * 5)
            child.stdin.close()
        assert child.stdout is not None
        seen = deque(maxlen=400)
        for line in child.stdout:
            text = line.decode("utf-8", "replace")
            seen.append(text)
            write(text)
        code = child.wait()
        if RUNNING is child:
            RUNNING = None
        if code != 0 or not gpkg.exists():
            hint = explain_failure("".join(seen))
            write(f"\nWatershed subset failed (exit {code}). DataStreamCLI was not started.\n")
            if hint:
                write(f"FIX: {hint}\n")
            return False
        write(f"Watershed geopackage written to {gpkg}\n")
    else:
        write(f"Watershed geopackage is already at {gpkg}\n")
    try:
        repairs = repair_watershed_ids(str(gpkg))
    except Exception as error:
        write(f"\n{error}\nWatershed ids were not renamed. DataStreamCLI was not started.\n")
        return False
    if repairs:
        lines = ", ".join(f"{item['from']} -> {item['to']}" for item in repairs)
        write(f"Renamed scientific-notation catchment ids in the watershed file: {lines}.\n")
    return True


class AppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, status: int, body) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _text(self, status: int, text: str) -> None:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        if length > 20_000:
            raise ValueError("too large")
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("bad")
        return body

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path in {"/", "/index.html"}:
            self._file(WEB / "index.html", "text/html; charset=utf-8")
            return
        if url.path == "/app.css":
            self._file(WEB / "app.css", "text/css; charset=utf-8")
            return
        if url.path == "/app.js":
            self._file(WEB / "app.js", "text/javascript; charset=utf-8")
            return
        if url.path == "/api/agent/key":
            self._json(200, {"loaded": api_key() != ""})
            return
        if url.path == "/api/catalog":
            self._json(200, {"forcings": FORCINGS, "realizations": REALIZATIONS, "defaultRealization": DEFAULT_REALIZATION})
            return
        if url.path == "/api/setup":
            self._json(200, {"problems": setup_problems(key_loaded=api_key() != "")})
            return
        query = parse_qs(url.query)
        if url.path in {"/api/datastream/log", "/api/datastream/live"}:
            gage = (query.get("gage") or [""])[0]
            output_dir = (query.get("outputDir") or [""])[0]
            root = output_root(gage, output_dir)
            if not root:
                self._json(400, {"path": "", "text": "", "exists": False, "truncated": False})
                return
            relative = "datastream-metadata/datastream_steps.txt" if url.path.endswith("log") else "logs/nextgenhydro.log"
            shown = log_path_for(gage, output_dir) if url.path.endswith("/log") else live_log_path_for(gage, output_dir)
            self._json(200, {"path": shown, **read_tail(root / relative)})
            return
        if url.path == "/api/datastream/result":
            gage = (query.get("gage") or [""])[0]
            output_dir = (query.get("outputDir") or [""])[0]
            root = output_root(gage, output_dir)
            if not root:
                self._json(400, {"path": "", "entries": [], "hydrograph": None})
                return
            directory = root / "ngen-run" / "outputs"
            entries = list_result_files(directory) if directory.is_dir() else []
            chart = None
            if (root / "ngen-run").is_dir():
                try:
                    chart = build_hydrograph(root, gage, (query.get("start") or [""])[0], (query.get("end") or [""])[0])
                except Exception:
                    chart = None
            self._json(200, {"path": result_path_for(gage, output_dir), "entries": entries, "hydrograph": chart})
            return
        if url.path == "/api/watershed/status":
            self._watershed_status((query.get("gage") or [""])[0])
            return
        if url.path == "/api/watershed/geojson":
            self._watershed_geojson((query.get("gage") or [""])[0])
            return
        self._text(404, "Not found.\n")

    def _file(self, path: Path, content_type: str) -> None:
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _watershed_status(self, gage: str) -> None:
        global WATERSHED_BUILD
        if not is_gage_id(gage):
            self._json(400, {"phase": "missing", "message": "Set a USGS gauge.", "log": "", "path": ""})
            return
        path = watershed_geopackage(gage)
        gpkg = Path(resolve_watershed_geopackage(gage, str(Path.home())))
        build = WATERSHED_BUILD if WATERSHED_BUILD and WATERSHED_BUILD.get("gage") == gage else None
        preparing = bool(WATERSHED_BUSY and build and not build.get("failed"))
        if gpkg.exists() and not preparing:
            self._json(200, {"phase": "ready", "message": "The geopackage is ready. Catchments and rivers are on the map.", "log": (build or {}).get("log", ""), "path": path})
            return
        if build and build.get("failed"):
            self._json(200, {"phase": "failed", "message": build.get("status", ""), "log": build.get("log", ""), "path": path})
            return
        if preparing and build:
            self._json(200, {"phase": "preparing", "message": build.get("status", ""), "log": build.get("log", ""), "path": path})
            return
        self._json(200, {"phase": "missing", "message": f"The watershed file for USGS {gage} is not on this computer yet.", "log": "", "path": path})

    def _watershed_geojson(self, gage: str) -> None:
        if not is_gage_id(gage):
            self._json(400, {"ready": False, "status": "Set a USGS gauge."})
            return
        gpkg = Path(resolve_watershed_geopackage(gage, str(Path.home())))
        if not gpkg.exists():
            build = WATERSHED_BUILD if WATERSHED_BUILD and WATERSHED_BUILD.get("gage") == gage else None
            if build and build.get("failed"):
                self._json(500, {"ready": False, "status": build.get("status", "")})
                return
            self._begin_watershed(gage)
            status = WATERSHED_BUILD.get("status") if WATERSHED_BUILD and WATERSHED_BUILD.get("gage") == gage else f"Building the watershed for USGS {gage}."
            self._json(202, {"ready": False, "status": status})
            return
        try:
            body = dict(watershed_geojson(str(gpkg)))
            body["name"] = lookup_station_name(gage) or ""
            self._json(200, body)
        except RuntimeError as error:
            if str(error) == "WATERSHED_WRITING":
                self._json(202, {"ready": False, "status": "The watershed file is still being written."})
                return
            self._json(500, {"ready": False, "status": str(error)})

    def _begin_watershed(self, gage: str) -> None:
        global WATERSHED_BUSY, WATERSHED_BUILD
        if WATERSHED_BUSY:
            return
        gpkg = Path(resolve_watershed_geopackage(gage, str(Path.home())))
        if gpkg.exists():
            return
        WATERSHED_BUSY = True
        WATERSHED_BUILD = {"gage": gage, "status": f"Building the watershed for USGS {gage}.", "failed": False, "log": ""}

        def run() -> None:
            global WATERSHED_BUSY

            def write(text: str) -> None:
                if not WATERSHED_BUILD or WATERSHED_BUILD.get("gage") != gage:
                    return
                clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
                WATERSHED_BUILD["log"] = (WATERSHED_BUILD["log"] + clean)[-80_000:]
                lines = [line.strip() for line in clean.split("\n") if line.strip()]
                if lines:
                    WATERSHED_BUILD["status"] = lines[-1]

            try:
                ready = ensure_watershed(gage, write)
                if WATERSHED_BUILD and WATERSHED_BUILD.get("gage") == gage and not ready:
                    WATERSHED_BUILD["failed"] = True
            finally:
                WATERSHED_BUSY = False

        threading.Thread(target=run, daemon=True).start()

    def do_POST(self) -> None:
        url = urlparse(self.path).path
        if url == "/api/agent/key":
            try:
                body = self._read_json()
            except Exception:
                self._json(400, {"loaded": api_key() != ""})
                return
            key = clean_api_key(body.get("key"))
            if not key:
                self._json(400, {"loaded": api_key() != ""})
                return
            path = KEY_FILES[0]
            try:
                path.write_text(key + "\n", encoding="utf-8")
                os.chmod(path, 0o600)
            except OSError:
                self._json(500, {"loaded": api_key() != ""})
                return
            self._json(200, {"loaded": True})
            return
        if url == "/api/ask":
            try:
                body = self._read_json()
            except Exception:
                self._json(400, {"usedModel": False, "note": "The sentence could not be read."})
                return
            sentence = body.get("sentence", "")
            sentence = sentence.strip() if isinstance(sentence, str) else ""
            if not sentence:
                self._json(400, {"usedModel": False, "note": "Write a sentence first."})
                return
            self._json(200, ask_sentence(sentence, body))
            return
        if url == "/api/hydrofabric/gages":
            try:
                body = self._read_json()
            except Exception:
                self._json(400, {"ids": []})
                return
            ids = body.get("ids") if isinstance(body.get("ids"), list) else []
            self._json(200, {"ids": nextgen_gage_ids([item for item in ids if isinstance(item, str)][:200])})
            return
        if url == "/api/datastream/stop":
            global RUNNING
            if RUNNING and RUNNING.poll() is None:
                RUNNING.terminate()
            self._text(200, "Stopped.\n")
            return
        if url == "/api/datastream/run":
            self._run()
            return
        if url == "/api/run/check":
            try:
                body = self._read_json()
            except Exception:
                self._json(400, {"problems": [{"field": "", "message": "The page sent a request the server could not read."}], "command": None})
                return
            checked = check_run(body)
            self._json(200, {"problems": checked["problems"], "command": checked["command"]})
            return
        self._text(404, "Not found.\n")

    def _run(self) -> None:
        global RUNNING, WATERSHED_BUSY
        if RUNNING and RUNNING.poll() is None:
            self._text(409, "A DataStreamCLI run is already going.\n")
            return
        if WATERSHED_BUSY:
            self._text(409, "The watershed file is still being prepared.\n")
            return
        try:
            body = self._read_json()
        except Exception:
            self._text(400, "The page sent a run request the server could not read. Reload the page and try again.\n")
            return
        checked = check_run(body)
        if checked["problems"]:
            self._text(checked["status"], problems_text(checked["problems"]) + "\n")
            return
        preview = checked["command"]
        gage = body.get("gage") or ""
        output_dir = body.get("outputDir") or ""
        self.send_response(200)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.send_header("cache-control", "no-cache")
        self.end_headers()
        WATERSHED_BUSY = True
        log_path = None
        buffered = ""

        def write(text: str) -> None:
            nonlocal log_path, buffered
            try:
                self.wfile.write(text.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
            if log_path is None:
                folder = output_root(gage, output_dir)
                shown = live_log_path_for(gage, output_dir)
                if folder and shown and folder.exists():
                    file = DATASTREAM_ROOT / shown
                    file.parent.mkdir(parents=True, exist_ok=True)
                    log_path = file.open("a", encoding="utf-8")
                    if buffered:
                        log_path.write(buffered)
                        buffered = ""
            if log_path:
                log_path.write(text)
                log_path.flush()
            else:
                buffered = (buffered + text)[-80_000:]

        try:
            ready = ensure_watershed(gage, write)
        except Exception as error:
            write(f"\n{error}\n")
            ready = False
        finally:
            WATERSHED_BUSY = False
        if not ready:
            if log_path:
                log_path.close()
            return
        argv = preview["argv"]
        shown = watershed_geopackage(gage)
        absolute = resolve_watershed_geopackage(gage, str(Path.home()))
        argv = [absolute if item == shown else item for item in argv]
        child = subprocess.Popen(
            ["bash", str(SCRIPT), *argv],
            cwd=DATASTREAM_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        RUNNING = child
        assert child.stdout is not None
        seen = deque(maxlen=400)
        for line in child.stdout:
            text = line.decode("utf-8", "replace")
            seen.append(text)
            write(text)
        code = child.wait()
        write(f"\nDataStreamCLI exited {code}.\n")
        if code != 0:
            hint = explain_failure("".join(seen))
            if hint:
                write(f"FIX: {hint}\n")
        if RUNNING is child:
            RUNNING = None
        if log_path:
            log_path.close()


def main() -> None:
    print(f"DataStreamCLI folder: {DATASTREAM_ROOT}", flush=True)
    problems = setup_problems(key_loaded=api_key() != "")
    if problems:
        print("Setup check found these problems:", flush=True)
        for item in problems:
            print(f"  - {item['message']} Fix: {item['fix']}", flush=True)
    else:
        print("Setup check passed.", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", 5180), AppHandler)
    print("NextGenHydro Python is at http://127.0.0.1:5180/", flush=True)
    server.serve_forever()
