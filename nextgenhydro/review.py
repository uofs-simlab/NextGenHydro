import re
from datetime import datetime, timezone

from .agent import EMPTY_PATCH, is_gage_id, named_location, sanitize_agent_patch
from .forcings import coverage_problem
from .forecast import plan_forecast
from .model_support import check_models
from .nlp import interpret_action, interpret_logging, interpret_realization
from .parse_request import align_hourly_time, hourly_clock_note, parse_request


def skips_forcing_download(sentence: str) -> bool:
    refused = re.search(r"\b(?:without|do not|don't|dont)\s+download(?:ing)?\s+forcing\b", sentence, re.I)
    existing = re.search(r"\bexisting\s+forcing\b", sentence, re.I)
    return refused is not None and existing is not None


def check_gauge(gage: str, sentence: str) -> dict:
    from .nextgen_gages import gage_in_hydrofabric
    from .site_name import lookup_station_name, lookup_station_point

    named = gage if is_gage_id(gage or "") else ""
    if not named:
        named = parse_request(sentence).get("gage") or ""
    if not is_gage_id(named):
        return {"ok": True, "gage": "", "message": ""}
    known = gage_in_hydrofabric(named)
    if known is False:
        return {
            "ok": False,
            "gage": "",
            "message": f"USGS {named} is not a NextGen gauge, so the gauge stays empty and this run is not ready.",
        }
    if known is not True:
        return {"ok": True, "gage": named, "message": ""}
    point = lookup_station_point(named)
    return {
        "ok": True,
        "gage": named,
        "latitude": None if not point else point["lat"],
        "longitude": None if not point else point["lng"],
        "location": lookup_station_name(named) or "",
        "message": f"USGS {named} is a NextGen gauge.",
    }


def check_coordinates(lat, lng, sentence: str) -> dict:
    from .agent import read_named_coordinates
    from .nearest_gages import lookup_nearest_gages
    from .nextgen_gages import nextgen_gage_ids

    named = read_named_coordinates(sentence)
    if named is None and lat is not None and lng is not None:
        named = {"lat": float(lat), "lng": float(lng), "valid": -90 <= float(lat) <= 90 and -180 <= float(lng) <= 180}
    if not named:
        return {"ok": True, "message": "", "gages": []}
    if not named["valid"]:
        problems = []
        if not -90 <= named["lat"] <= 90:
            problems.append(f"latitude {named['lat']:g} is outside -90 to 90")
        if not -180 <= named["lng"] <= 180:
            problems.append(f"longitude {named['lng']:g} is outside -180 to 180")
        reason = " and ".join(problems)
        return {
            "ok": False,
            "clear": True,
            "message": f"{reason[:1].upper()}{reason[1:]}, so this run is not ready.",
            "gages": [],
        }
    if is_gage_id(parse_request(sentence).get("gage") or ""):
        return {"ok": True, "lat": named["lat"], "lng": named["lng"], "message": "", "gages": []}
    origin = {"lat": named["lat"], "lng": named["lng"]}
    gages = lookup_nearest_gages(origin, nextgen_gage_ids)
    if not gages:
        return {
            "ok": False,
            "lat": named["lat"],
            "lng": named["lng"],
            "message": "No NextGen gauge was found at that point, so the gauge number stays empty and this run is not ready.",
            "gages": [],
        }
    nearest = gages[0]
    return {
        "ok": True,
        "lat": named["lat"],
        "lng": named["lng"],
        "gage": nearest["id"],
        "location": nearest.get("name") or "",
        "message": f"The nearest NextGen gauge is USGS {nearest['id']}.",
        "gages": gages,
    }


def check_dates(start: str, end: str, sentence: str = "", now=None) -> dict:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", start or "") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", end or ""):
        return {"ok": True, "message": ""}
    if end <= start:
        return {
            "ok": False,
            "message": f"Start {start.replace('T', ' ')} is not before end {end.replace('T', ' ')}, so this run is not ready.",
        }
    if sentence and re.search(r"\bforecast", sentence, re.I):
        try:
            ended = datetime.strptime(end, "%Y-%m-%dT%H:%M")
        except ValueError:
            ended = None
        clock = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
        if ended and ended <= clock:
            return {
                "ok": False,
                "message": "Those dates are already in the past. A forecast covers upcoming hours, so this time range is not for forecasting and this run is not ready.",
            }
    return {"ok": True, "message": ""}


def stated_output_dir(sentence: str) -> str:
    from .agent import is_safe_output_dir

    match = re.search(
        r"\b(?:output|results?)\s+(?:folder|directory|dir|path)\s*(?:to|as|named|called|at|in|is|=|:)?\s*[\"'`]?([~/.\w][^\s\"'`,;]*)",
        sentence,
        re.I,
    )
    if not match:
        return ""
    folder = match.group(1).rstrip(".")
    if not folder or ".." in re.split(r"[/\\]", folder) or len(folder) > 500 or not is_safe_output_dir(folder):
        return ""
    return folder


def _missing_for_run(patch: dict) -> str:
    missing = []
    if not patch.get("start") or not patch.get("end"):
        missing.append("Start and End dates")
    if not patch.get("forcing"):
        missing.append("a Forcing")
    if not missing:
        return ""
    return f"The sentence gives no {' or '.join(missing)}. Fill {' and '.join(missing)} in the form before Run."


def _draft_models(draft: dict | None) -> list:
    from .model_support import catalog_model_names

    raw = (draft or {}).get("models")
    return catalog_model_names(raw if isinstance(raw, list) else [])


def review_plan(sentence: str, draft: dict | None = None, now=None) -> dict:
    asked = _draft_models(draft)
    incoming = sanitize_agent_patch(draft or {})
    parsed = parse_request(sentence)
    start = align_hourly_time(incoming.get("start") or parsed.get("start") or "")
    end = align_hourly_time(incoming.get("end") or parsed.get("end") or "")
    gauge = check_gauge(incoming.get("gage") or "", sentence)
    coordinates = check_coordinates(incoming.get("lat"), incoming.get("lng"), sentence)
    dates = check_dates(start, end, sentence, now)
    patch = {**EMPTY_PATCH, **incoming, "start": start, "end": end, "gage": gauge.get("gage") or "", "outputDir": stated_output_dir(sentence)}
    if coordinates.get("clear"):
        patch["gage"] = ""
        patch["lat"] = None
        patch["lng"] = None
        patch["location"] = ""
    elif coordinates.get("gage"):
        patch["gage"] = coordinates["gage"]
        patch["lat"] = coordinates["lat"]
        patch["lng"] = coordinates["lng"]
        patch["location"] = coordinates.get("location") or ""
    elif coordinates.get("lat") is not None:
        patch["lat"] = coordinates["lat"]
        patch["lng"] = coordinates["lng"]
    elif gauge.get("latitude") is not None:
        patch["lat"] = gauge["latitude"]
        patch["lng"] = gauge["longitude"]
    if not coordinates.get("clear") and not coordinates.get("gage"):
        place = named_location(sentence, "" if gauge.get("gage") else incoming.get("location", ""))
        patch["location"] = place or gauge.get("location") or incoming.get("location") or ""
    action = interpret_action(sentence) or incoming.get("action") or ""
    if not gauge.get("ok", True) or not coordinates.get("ok", True) or not dates.get("ok", True):
        action = "do not run"
    patch["action"] = action
    patch["logging"] = interpret_logging(sentence)
    patch["nprocs"] = incoming.get("nprocs") or 4
    messages = [item["message"] for item in (gauge, coordinates, dates) if item.get("message")]
    if skips_forcing_download(sentence):
        patch["forcing"] = ""
        messages.append("Forcing stays empty because the sentence says not to download forcing data and not to use existing forcing files.")
    elif dates.get("ok", True):
        forecast = plan_forecast(patch.get("forcing") or "", patch["start"], patch["end"], now)
        if forecast:
            patch["forcing"] = forecast["forcing"]
            patch["start"] = forecast["start"]
            patch["end"] = forecast["end"]
            messages.append(forecast["message"])
            if not forecast["ok"]:
                action = "do not run"
                patch["action"] = action
    chosen = interpret_realization(sentence, asked, incoming.get("realization") or "")
    if chosen.get("source") == "unsupported":
        patch["realization"] = ""
        action = "do not run"
        patch["action"] = action
        if chosen.get("note"):
            messages.append(chosen["note"])
    elif chosen.get("source") == "named":
        patch["realization"] = chosen.get("realization") or patch.get("realization") or ""
        if chosen.get("note"):
            messages.append(chosen["note"])
    elif chosen.get("source") == "chosen":
        if action in {"run", "dry run"} and not patch.get("realization"):
            patch["realization"] = chosen["realization"]
        if chosen.get("note"):
            messages.append(chosen["note"])
    clock = hourly_clock_note(incoming.get("start") or parsed.get("start") or "", incoming.get("end") or parsed.get("end") or "")
    if clock:
        messages.append(clock)
    outside = coverage_problem(patch.get("forcing") or "", patch.get("start") or "", patch.get("end") or "")
    if outside:
        messages.append(outside)
    if patch.get("forcing") == "NWM_RETRO_V3" and re.search(r"\bAORC\b", sentence, re.I):
        messages.append("AORC is read as NWM v3 retrospective, whose forcing over the US is built from AORC.")
    if action in {"run", "dry run"} and not skips_forcing_download(sentence):
        missing = _missing_for_run(patch)
        if missing:
            messages.append(missing)
    if patch["outputDir"]:
        messages.append(f"Output folder {patch['outputDir']} is taken from the sentence.")
    return {
        "patch": patch,
        "messages": messages,
        "gages": coordinates.get("gages") or [],
        "askedModels": asked,
        "checks": {"check_gauge": gauge, "check_coordinates": coordinates, "check_dates": dates, "check_models": check_models(sentence, asked)},
    }


def note_from_feedback(model_note: str, messages: list[str]) -> str:
    facts = [message for message in messages if message]
    note = re.sub(r"\s+", " ", model_note or "").strip()
    if not facts:
        return note
    if note and _follows_feedback(note, facts):
        return note
    return " ".join(facts)


def _follows_feedback(note: str, facts: list[str]) -> bool:
    false_claim = re.search(r"not a NextGen (?:station|gage|gauge)", note, re.I)
    feedback_rejects = any(re.search(r"not a NextGen (?:station|gage|gauge)", fact, re.I) for fact in facts)
    if false_claim and not feedback_rejects:
        return False
    if re.search(r"no model was named", note, re.I) and not any(re.search(r"no model was named", fact, re.I) for fact in facts):
        return False
    if re.search(r"not supported in this repo", note, re.I) and not any(re.search(r"not supported in this repo", fact, re.I) for fact in facts):
        return False
    keys = (
        "not a NextGen gauge",
        "is a NextGen gauge",
        "not before",
        "outside -90 to 90",
        "outside -180 to 180",
        "Forcing stays empty",
        "No model was named",
        "modeling framework",
        "not a catchment model",
        "not supported in this repo",
        "This is a forecast",
        "already in the past",
        "not for forecasting",
        "nearest NextGen gauge",
        "No NextGen gauge was found",
        "AORC",
        "forcing covers",
        "before Run",
        "Output folder",
    )
    for fact in facts:
        if fact in note:
            continue
        needed = [key for key in keys if key in fact]
        if not needed or any(key not in note for key in needed):
            return False
    return True
