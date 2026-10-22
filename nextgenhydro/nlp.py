import re
from datetime import datetime, timedelta, timezone

from .forcings import FORCINGS
from .parse_request import parse_request
from .realizations import DEFAULT_REALIZATION, REALIZATIONS, is_realization_id, read_realization


def _refuses_run(sentence: str) -> bool:
    stopped = r"run|running|simulate|simulating|simulation|execute|executing|execution"
    return (
        re.search(
            rf"\b(?:do not|don't|dont|without)\s+(?:a\s+|the\s+)?(?:{stopped})\b",
            sentence,
            re.I,
        )
        is not None
        or re.search(
            rf"\bstop\s+before\s+(?:the\s+|a\s+|any\s+)?(?:model\s+|nextgen\s+)?(?:{stopped})\b",
            sentence,
            re.I,
        )
        is not None
    )


def _asks_for_forcing(sentence: str) -> bool:
    return re.search(r"\bforcing(?:\s+data)?\b", sentence, re.I) is not None


def _asks_to_run(sentence: str) -> bool:
    if _refuses_run(sentence):
        return False
    return re.search(r"\b(?:run|simulate|simulation|execute|executing|execution)\b", sentence, re.I) is not None


def _asks_for_realization(sentence: str) -> bool:
    return re.search(r"\b(?:realizations?|bmi|model inputs)\b", sentence, re.I) is not None


def _asks_for_workflow(sentence: str) -> bool:
    return re.search(r"\b(?:complete workflow|workflow plan|complete plan)\b", sentence, re.I) is not None


def _asks_for_dry_run(sentence: str) -> bool:
    return re.search(r"\bdry[\s-]?run\b", sentence, re.I) is not None


DEFAULT_NPROCS = 4


def interpret_nprocs(sentence: str) -> int:
    match = re.search(
        r"\b(?:nprocs?|processes|processors|cores)\s*[:=]?\s*(\d{1,3})\b|\b(\d{1,3})\s*(?:nprocs?|processes|processors|cores)\b",
        sentence,
        re.I,
    )
    if not match:
        return DEFAULT_NPROCS
    value = int(match.group(1) or match.group(2))
    if value < 1:
        return DEFAULT_NPROCS
    return min(value, 256)


def interpret_logging(sentence: str) -> str:
    if re.search(r"\bverbose(?:\s+log(?:ging)?)?\b", sentence, re.I):
        return "verbose"
    return ""


def interpret_action(sentence: str) -> str:
    if _refuses_run(sentence):
        return "do not run"
    if _asks_for_dry_run(sentence):
        return "dry run"
    if _asks_to_run(sentence):
        return "run"
    return ""


def _unnamed_label() -> str:
    for item in REALIZATIONS:
        if item["id"] == DEFAULT_REALIZATION:
            return item["label"]
    return DEFAULT_REALIZATION


NLP_RULES = [
    {
        "id": "unnamed-model",
        "prompt": "Run a NextGen simulation for the watershed draining to USGS gage 01646500 from January 1, 2020, to January 10, 2020.",
        "realization": DEFAULT_REALIZATION,
        "note": f"No model was named. Choose {_unnamed_label()}.",
    }
]


def _historical_period(iso: str) -> bool:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso)
    if not match:
        return False
    end = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    return end < cutoff


def interpret_forcing(sentence: str, dates: dict | None = None) -> dict:
    parsed = dates if dates is not None else parse_request(sentence)
    if parsed.get("forcing"):
        return {"forcing": parsed["forcing"], "source": "named", "note": ""}
    period = parsed.get("end") or parsed.get("start") or ""
    label = next((item["label"] for item in FORCINGS if item["id"] == "NWM_RETRO_V3"), "NWM_RETRO_V3")
    if period and _historical_period(period):
        return {
            "forcing": "NWM_RETRO_V3",
            "source": "chosen",
            "note": f"No forcing was named. The dates are in the past, so choose {label}. The Forcing field can be switched to v2 retrospective.",
        }
    if (_asks_for_workflow(sentence) or _asks_for_forcing(sentence)) and not period:
        reason = "this workflow plan" if _asks_for_workflow(sentence) else "the requested forcing"
        return {
            "forcing": "NWM_RETRO_V3",
            "source": "chosen",
            "note": f"No forcing was named. Choose {label} for {reason}. The Forcing field can be switched to v2 retrospective.",
        }
    return {"forcing": "", "source": "none", "note": ""}


def _covered_by_realization(name: str, realization: str) -> bool:
    from .model_support import _norm

    parts = {
        "realization_rust_lstm.json": {"rust", "lstm", "lstmrust", "rustlstm"},
        "realization_rust_lstm_troute.json": {"rust", "lstm", "lstmrust", "rustlstm", "troute"},
        "realization_python_lstm_troute.json": {"python", "lstm", "pythonlstm", "troute"},
        "realization_sloth_nom_cfe_pet.json": {"sloth", "noah", "noahowp", "noahowpmodular", "cfe", "pet"},
        "realization_sloth_nom_cfe_pet_troute.json": {"sloth", "noah", "noahowp", "noahowpmodular", "cfe", "pet", "troute"},
        "realization_sloth_troute.json": {"sloth", "troute"},
    }
    return _norm(name) in parts.get(realization, set())


def _excludes_model(sentence: str, name: str) -> bool:
    parts = [re.escape(part) for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    if not parts:
        return False
    target = r"[^A-Za-z0-9]*".join(parts)
    return re.search(
        rf"\b(?:without|not using|do not use|don't use|dont use)\b(?:\s+\w+){{0,6}}\s+{target}\b",
        sentence,
        re.I,
    ) is not None


def realization_for_resolved(sentence: str, names: list | None) -> str:
    from .model_support import _appears, _norm

    keys = {_norm(name) for name in names or [] if isinstance(name, str)}
    wants_troute = ("troute" in keys or _appears(sentence, "t-route")) and not _excludes_model(sentence, "t-route")
    python_lstm = "pythonlstm" in keys or ("python" in keys and "lstm" in keys)
    lstm_rust = bool(keys & {"lstmrust", "rustlstm"}) or ("rust" in keys and "lstm" in keys)
    noah_stack = bool(keys & {"noah", "noahowp", "noahowpmodular", "cfe", "pet"})
    sloth = "sloth" in keys
    if python_lstm:
        return "realization_python_lstm_troute.json"
    if lstm_rust:
        return "realization_rust_lstm_troute.json" if wants_troute else "realization_rust_lstm.json"
    if sloth and wants_troute and not noah_stack:
        return "realization_sloth_troute.json"
    if noah_stack:
        return "realization_sloth_nom_cfe_pet_troute.json" if wants_troute else "realization_sloth_nom_cfe_pet.json"
    return ""


def interpret_realization(sentence: str, names: list | None = None, preferred: str = "") -> dict:
    from .model_support import unsupported_models, unsupported_note

    if names is not None or preferred:
        resolved = realization_for_resolved(sentence, names)
        if resolved and (not preferred or not is_realization_id(preferred)):
            preferred = resolved
        elif resolved and _excludes_model(sentence, "t-route") and "troute" in preferred:
            preferred = resolved
        missing = unsupported_models(sentence, names)
        if preferred and is_realization_id(preferred):
            missing = [name for name in missing if not _covered_by_realization(name, preferred)]
            if not missing:
                return {"realization": preferred, "source": "named", "note": ""}
            return {"realization": "", "source": "unsupported", "note": unsupported_note(missing)}
        if missing:
            return {"realization": "", "source": "unsupported", "note": unsupported_note(missing)}
        if not names and (_asks_to_run(sentence) or _asks_for_realization(sentence) or _asks_for_workflow(sentence)):
            rule = NLP_RULES[0]
            return {"realization": rule["realization"], "source": "chosen", "note": rule["note"]}
        return {"realization": "", "source": "none", "note": ""}
    named = read_realization(sentence)
    missing = unsupported_models(sentence, names)
    if named:
        return {"realization": named, "source": "named", "note": unsupported_note(missing)}
    if missing:
        return {"realization": "", "source": "unsupported", "note": unsupported_note(missing)}
    if _asks_to_run(sentence) or _asks_for_realization(sentence) or _asks_for_workflow(sentence):
        rule = NLP_RULES[0]
        return {"realization": rule["realization"], "source": "chosen", "note": rule["note"]}
    return {"realization": "", "source": "none", "note": ""}


def agent_system_prompt() -> str:
    choices = "; ".join(f"{item['label']} = {item['id']}" for item in REALIZATIONS)
    return " ".join(
        [
            "You fill the NextGenHydro run form from one sentence.",
            "Set gage, start, and end only when this sentence names them. Otherwise use an empty string.",
            "Do not copy a gage, a date, a forcing, or a folder from an earlier sentence.",
            "A named month such as January 2020 is that whole month. Start is midnight on the first day and end is midnight on the last day.",
            "Call check_gauge, check_coordinates, check_dates, and check_models before the final plan.",
            "check_gauge says whether the gauge digits are in the NextGen hydrofabric. check_coordinates says whether latitude and longitude are in range. check_dates says whether the start is before the end.",
            "Read the sentence and decide which models it means. Do not match words in isolation.",
            "Noah, Noah-OWP, and Noah-OWP-Modular are the same model.",
            "Rust and LSTM together are one model, LSTM Rust. There is no separate model named rust, and there is no model named lstmrust.",
            "LSTM Rust without t-route uses realization_rust_lstm.json. LSTM Rust with t-route uses realization_rust_lstm_troute.json.",
            "t-route is the routing model. A sentence that asks for routing, channel routing, streamflow routing, or a compatible routing configuration asks for t-route, even when it does not write the word t-route.",
            "A compatible PET formulation, potential evapotranspiration, or evapotranspiration means PET.",
            "Words such as without, not using, and do not use exclude that model from the realization.",
            "Pass the resolved catalog name to check_models, such as LSTM Rust or Noah-OWP-Modular. Do not pass one piece of a package, such as rust, as its own model.",
            "check_models searches the DataStreamCLI model list for those resolved names. When a resolved name is a model and that list does not include it, leave realization empty, set action to do not run, and write that the model is not supported in this repo for now. Do not say that no model was named, and do not choose the default stack.",
            "Write the note from the messages those functions return. Do not add a hydrofabric judgment they did not return.",
            "When the gage number is in the NextGen hydrofabric, the app fills latitude and longitude from that USGS site.",
            "Latitude is a number from -90 to 90. Longitude is a number from -180 to 180.",
            "When the sentence gives a latitude or longitude outside that range, leave lat and lng null, leave location empty, say the coordinate is outside the range, and set action to do not run.",
            "When the sentence gives a latitude and a longitude inside that range and no gauge number, set lat and lng to those numbers. The app fills the nearest NextGen gauge.",
            "Dates are YYYY-MM-DDTHH:mm, midnight when no clock is given.",
            "These writings are the same span, start 2020-07-01T00:00 and end 2020-07-07T00:00: July 1–7, 2020; 2020/July/01, 2020/July/07; 2020-July-01 - 2020-July-07; 2020-07-01 - 2020-07-07; 2020/07/01 - 2020/07/07; 2020\\07\\01 - 2020\\07\\07; and the first week of July 2020.",
            "A comma between two dates is the same as a dash. Slashes, hyphens, and backslashes are the same separators.",
            "A year and four digits with one separator, such as 2002/0402, is that year, month, and day: 2002-04-02.",
            "Forcing is hourly. Write start and end with minutes 00. A time such as 23:59 becomes that hour at 00.",
            "The start must be before the end. When it is not, keep the named dates, say in the note that the start is not before the end, and set action to do not run.",
            "A river or basin name is not a USGS gage. Leave gage empty unless the sentence gives the gage digits.",
            "When the sentence gives gauge digits, copy those digits into gage. Do not decide whether that number is in the NextGen hydrofabric, and do not say it is not a NextGen gauge. The app checks and writes that only when the number is absent.",
            "When the sentence says not to download forcing and not to use existing forcing files, leave forcing empty. That does not clear the gauge and it does not set action to do not run.",
            "You read the place. location is that place in the sentence's own words.",
            "A watershed near Denver has location Denver. A watershed in Colorado has location Colorado. Bow River has location Bow River.",
            "Keep that place when the sentence also has a gage number. Do not replace Colorado with a station name.",
            "When the sentence names a place and gives no gage digits, leave gage empty. The app lists NextGen stations near your location.",
            "When the sentence gives a gage number and does not name a place, put the USGS station name in location if you know it. Otherwise leave location empty.",
            "forcing must be one of the allowed ids or an empty string.",
            "When the sentence names a forcing, use that id.",
            "When the sentence does not name a forcing and the dates are more than 45 days ago, set forcing to NWM_RETRO_V3.",
            "When the sentence asks for historical data, the latest historical record, a complete workflow plan, or forcing data, and does not name a forcing, set forcing to NWM_RETRO_V3 even if no dates are given.",
            "Say in the note that no forcing was named and v3 retrospective was chosen. v2 retrospective is the other historical archive.",
            "Leave forcing empty when the sentence does not ask for forcing, historical data, or a workflow plan and has no dates, or when the dates are recent enough for a forecast product.",
            f"realization must be one of: {choices}.",
            "When the sentence names Noah-OWP, CFE, or PET and does not ask for t-route or routing, use realization_sloth_nom_cfe_pet.json.",
            "When the sentence names Noah-OWP, CFE, or PET and asks for t-route or routing, use realization_sloth_nom_cfe_pet_troute.json.",
            "When the sentence names Rust LSTM and does not ask for t-route or routing, use realization_rust_lstm.json.",
            "When the sentence names Rust LSTM and asks for t-route or routing, use realization_rust_lstm_troute.json.",
            "When the sentence names Python LSTM, use realization_python_lstm_troute.json.",
            "When the sentence names SLOTH and t-route without CFE, PET, or Noah-OWP, use realization_sloth_troute.json.",
            "When the sentence asks for a realization, a realization configuration, BMI inputs, model inputs, or a complete workflow plan, look for a named model. If none is named, set realization to realization_sloth_nom_cfe_pet_troute.json.",
            "When the sentence asks to run or simulate and does not name a model, set realization to realization_sloth_nom_cfe_pet_troute.json.",
            "That choice is CFE, PET, Noah-OWP, and t-route. Say in the note that no model was named and that stack was chosen.",
            "A request not to run still keeps that realization when the sentence asked for one.",
            "action is dry run when the sentence asks for a dry run. A dry run still fills the gage, dates, forcing, and realization.",
            "action is run when the sentence asks to run, simulate, or execute and does not ask for a dry run.",
            "action is do not run when the sentence says not to run, not to simulate, not to execute, or to stop before model execution, including without executing NextGen.",
            "Stopping before model execution does not choose a realization. Leave realization empty unless the sentence asks for a model or a run.",
            "action is an empty string when the sentence says neither.",
            "logging is verbose when the sentence asks for verbose logging. Otherwise logging is an empty string.",
            "nprocs is the process count for DataStreamCLI. Use 4 unless the sentence names a count, such as 8 processes.",
            "outputDir is an empty string unless the user specifically mentioned it. The user types the output folder. Do not invent a folder name.",
            "note is one short sentence about what you filled.",
            "Do not invent a gage or a date. Do not set log paths, result paths, or the live log.",
        ]
    )
