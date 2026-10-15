import re

from .forcings import is_forcing_id
from .nlp import interpret_forcing, interpret_realization
from .parse_request import align_hourly_time, hourly_clock_note, merge_request, parse_request
from .place_query import place_query_from_sentence
from .realizations import is_realization_id
from .site_name import lookup_station_name

EMPTY_PATCH = {
    "gage": "",
    "start": "",
    "end": "",
    "forcing": "",
    "realization": "",
    "lat": None,
    "lng": None,
    "outputDir": "",
    "location": "",
    "note": "",
}


def is_gage_id(value: str) -> bool:
    return re.fullmatch(r"\d{7,15}", value or "") is not None


def is_safe_output_dir(value: str) -> bool:
    return "\x00" not in value and "\r" not in value and "\n" not in value


def is_iso_date_time(value: str) -> bool:
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", value or "")
    if not match:
        return False
    year, month, day, hour, minute = (int(part) for part in match.groups())
    if year < 1970 or year > 2100 or month < 1 or month > 12 or day < 1 or hour > 23 or minute > 59:
        return False
    from .parse_request import to_iso

    return to_iso(year, month, day, hour, minute) == value


def _clean_date(value) -> str:
    if not isinstance(value, str):
        return ""
    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T ](\d{2}):(\d{2})(?::\d{2})?)?", value.strip())
    if not match:
        return ""
    iso = f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}T{match.group(4) or '00'}:{match.group(5) or '00'}"
    return iso if is_iso_date_time(iso) else ""


def _clean_coord(value, low: float, high: float) -> float | None:
    number = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value.strip()):
        number = float(value.strip())
    if number is None or number < low or number > high:
        return None
    return number


def _clean_location(value) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", re.sub(r"[\x00\r\n]+", " ", value)).strip()[:120]
    if not text or is_gage_id(text):
        return ""
    return text


def named_location(sentence: str, proposed: str = "") -> str:
    offered = _clean_location(proposed)
    if offered:
        return offered
    return place_query_from_sentence(sentence) or ""


def location_after_gage_pick(current_location: str, gage_name: str) -> str:
    named = current_location.strip()
    if named:
        return named
    return gage_name.strip()


def _mention_location(note: str, location: str) -> str:
    if not location or location in note:
        return note
    return " ".join(part for part in [note, f"Location is {location}."] if part)


def _clean_note(value) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[\x00\r\n]+", " ", value)).strip()[:280]


def sanitize_agent_patch(value) -> dict:
    raw = value if isinstance(value, dict) else {}
    forcing = raw.get("forcing")
    realization = raw.get("realization")
    output_dir = raw.get("outputDir")
    return {
        "gage": raw.get("gage") if isinstance(raw.get("gage"), str) and is_gage_id(raw["gage"]) else "",
        "start": _clean_date(raw.get("start")),
        "end": _clean_date(raw.get("end")),
        "forcing": forcing if isinstance(forcing, str) and is_forcing_id(forcing) else "",
        "realization": realization if isinstance(realization, str) and is_realization_id(realization) else "",
        "lat": _clean_coord(raw.get("lat"), -90, 90),
        "lng": _clean_coord(raw.get("lng"), -180, 180),
        "outputDir": output_dir.strip() if isinstance(output_dir, str) and is_safe_output_dir(output_dir) else "",
        "location": _clean_location(raw.get("location")),
        "note": _clean_note(raw.get("note")),
    }


def apply_agent_patch(current: dict, patch: dict) -> dict:
    output_dir = patch.get("outputDir", "").strip()
    outlet = current.get("outlet")
    lat = patch["lat"] if patch.get("lat") is not None else (outlet or {}).get("lat")
    lng = patch["lng"] if patch.get("lng") is not None else (outlet or {}).get("lng")
    next_outlet = outlet
    if lat is not None and lng is not None:
        next_outlet = {"lat": lat, "lng": lng}
    elif patch.get("lat") is None and patch.get("lng") is None:
        next_outlet = outlet
    return {
        "request": merge_request(
            current.get("request") or {},
            {"gage": patch.get("gage", ""), "start": patch.get("start", ""), "end": patch.get("end", ""), "forcing": patch.get("forcing", "")},
        ),
        "runOptions": {
            "outputDir": output_dir or (current.get("runOptions") or {}).get("outputDir", ""),
            "realization": patch.get("realization") or (current.get("runOptions") or {}).get("realization", ""),
        },
        "outlet": next_outlet,
    }


def _read_sentence(sentence: str) -> dict:
    dates = parse_request(sentence)
    model = interpret_realization(sentence)
    weather = interpret_forcing(sentence, dates)
    return {
        **dates,
        "forcing": weather["forcing"],
        "forcingNote": weather["note"],
        "forcingSource": weather["source"],
        "realization": model["realization"],
        "realizationNote": model["note"],
        "realizationSource": model["source"],
    }


def _choice_note(patch_note: str, extras: list[str]) -> str:
    missing = [item for item in extras if item and item not in patch_note]
    return " ".join(part for part in [patch_note, *missing] if part)


def with_hourly_clocks(patch: dict) -> dict:
    start = align_hourly_time(patch.get("start", ""))
    end = align_hourly_time(patch.get("end", ""))
    clock_note = hourly_clock_note(patch.get("start", ""), patch.get("end", ""))
    if not clock_note:
        return patch
    return {**patch, "start": start, "end": end, "note": " ".join(part for part in [patch.get("note", ""), clock_note] if part)}


def fill_gaps(patch: dict, sentence: str) -> dict:
    local = _read_sentence(sentence)
    forcing = patch.get("forcing") or local["forcing"] if local["forcingSource"] == "none" else local["forcing"]
    return {
        **patch,
        "gage": local["gage"],
        "start": local["start"],
        "end": local["end"],
        "forcing": forcing,
        "realization": local["realization"],
        "location": named_location(sentence, patch.get("location", "")),
        "note": _choice_note(patch.get("note", ""), [local["realizationNote"], local["forcingNote"]]),
    }


def fallback_answer(sentence: str) -> dict:
    parsed = _read_sentence(sentence)
    found = [
        name
        for name, present in [
            ("gage", parsed["gage"]),
            ("start", parsed["start"]),
            ("end", parsed["end"]),
            ("forcing", parsed["forcingSource"] == "named"),
            ("realization", parsed["realizationSource"] == "named"),
        ]
        if present
    ]
    if not found and not parsed["realizationNote"] and not parsed["forcingNote"]:
        base = "The model was not used. Nothing in that sentence filled the form."
    else:
        base = f"The model was not used. Read {', '.join(found)} from that sentence."
    location = named_location(sentence)
    note = _mention_location(_choice_note(base, [parsed["realizationNote"], parsed["forcingNote"]]), location)
    patch = with_hourly_clocks({**EMPTY_PATCH, **parsed, "location": location, "note": note})
    return {"patch": patch, "note": patch["note"], "usedModel": False}


def with_station_location(patch: dict) -> dict:
    if patch.get("location", "").strip() or not is_gage_id(patch.get("gage", "")):
        return patch
    name = lookup_station_name(patch["gage"])
    if not name:
        return patch
    note = _mention_location(patch.get("note", ""), name)
    return {**patch, "location": name, "note": note}


def note_for_ask(answer: dict, merged: dict) -> str:
    if answer.get("usedModel"):
        return answer.get("note") or "Filled the form from that sentence."
    patch = answer["patch"]
    named = patch.get("gage") or patch.get("start") or patch.get("end") or patch.get("forcing") or patch.get("realization")
    if not named:
        return answer.get("note", "")
    still_open = ", ".join(
        label
        for label, missing in [
            ("gage", not merged.get("gage")),
            ("start", not merged.get("start")),
            ("end", not merged.get("end")),
            ("forcing", not merged.get("forcing")),
        ]
        if missing
    )
    if still_open:
        return f"{answer.get('note', '')} Still open: {still_open}."
    return f"{answer.get('note', '')} The request is complete."


def finish_ask(answer: dict) -> dict:
    patch = with_station_location(answer["patch"])
    return {**answer, "patch": patch, "note": patch.get("note", "")}
