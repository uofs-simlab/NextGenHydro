import re
from datetime import datetime, timedelta, timezone

from .forcings import FORCINGS
from .parse_request import parse_request
from .realizations import DEFAULT_REALIZATION, REALIZATIONS, read_realization


def _refuses_run(sentence: str) -> bool:
    return (
        re.search(
            r"\b(?:do not|don't|dont|without)\s+(?:a\s+|the\s+)?(?:run|running|simulate|simulating|simulation)\b",
            sentence,
            re.I,
        )
        is not None
    )


def _asks_to_run(sentence: str) -> bool:
    if _refuses_run(sentence):
        return False
    return re.search(r"\b(?:run|simulate|simulation)\b", sentence, re.I) is not None


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
        "note": f"No model was named. Chose {_unnamed_label()}.",
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
    if not period or not _historical_period(period):
        return {"forcing": "", "source": "none", "note": ""}
    label = next((item["label"] for item in FORCINGS if item["id"] == "NWM_RETRO_V3"), "NWM_RETRO_V3")
    return {
        "forcing": "NWM_RETRO_V3",
        "source": "chosen",
        "note": f"No forcing was named. The dates are in the past, so chose {label}. The Forcing field can be switched to v2 retrospective.",
    }


def interpret_realization(sentence: str) -> dict:
    named = read_realization(sentence)
    if named:
        return {"realization": named, "source": "named", "note": ""}
    if _asks_to_run(sentence) and read_realization(sentence) == "":
        rule = NLP_RULES[0]
        return {"realization": rule["realization"], "source": "chosen", "note": rule["note"]}
    return {"realization": "", "source": "none", "note": ""}


def agent_system_prompt() -> str:
    choices = "; ".join(f"{item['label']} = {item['id']}" for item in REALIZATIONS)
    return " ".join(
        [
            "You fill the NextGenHydro run form from one sentence.",
            "Set gage, start, end, and outputDir only when this sentence names them. Otherwise use an empty string.",
            "Do not copy a gage, a date, a forcing, or a folder from an earlier sentence.",
            "A named month such as January 2020 is that whole month. Start is midnight on the first day and end is midnight on the last day.",
            "Use null for lat and lng when the sentence does not give that coordinate.",
            "Dates are YYYY-MM-DDTHH:mm, midnight when no clock is given.",
            "These writings are the same span, start 2020-07-01T00:00 and end 2020-07-07T00:00: July 1–7, 2020; 2020/July/01, 2020/July/07; 2020-July-01 - 2020-July-07; 2020-07-01 - 2020-07-07; 2020/07/01 - 2020/07/07; 2020\\07\\01 - 2020\\07\\07; and the first week of July 2020.",
            "A comma between two dates is the same as a dash. Slashes, hyphens, and backslashes are the same separators.",
            "Forcing is hourly. Write start and end with minutes 00. A time such as 23:59 becomes that hour at 00.",
            "A river or basin name is not a USGS gage. Leave gage empty unless the sentence gives the gage digits.",
            "You read the place. location is that place in the sentence's own words.",
            "A watershed near Denver has location Denver. A watershed in Colorado has location Colorado. Bow River has location Bow River.",
            "Keep that place when the sentence also has a gage number. Do not replace Colorado with a station name.",
            "When the sentence names a place and gives no gage digits, leave gage empty. The app lists NextGen stations near your location.",
            "When the sentence gives a gage number and does not name a place, put the USGS station name in location if you know it. Otherwise leave location empty.",
            "forcing must be one of the allowed ids or an empty string.",
            "When the sentence names a forcing, use that id.",
            "When the sentence does not name a forcing and the dates are more than 45 days ago, set forcing to NWM_RETRO_V3.",
            "When the sentence asks for historical data or the latest historical record and does not name a forcing, set forcing to NWM_RETRO_V3 even if no dates are given.",
            "Say in the note that no forcing was named and v3 retrospective was chosen. v2 retrospective is the other historical archive.",
            "Leave forcing empty when the sentence does not ask for historical data and has no dates, or when the dates are recent enough for a forecast product.",
            f"realization must be one of: {choices}.",
            "When the sentence names Noah-OWP, CFE, or PET without t-route, use realization_sloth_nom_cfe_pet.json.",
            "When the sentence names Noah-OWP, CFE, or PET with t-route, use realization_sloth_nom_cfe_pet_troute.json.",
            "When the sentence names Rust LSTM without t-route, use realization_rust_lstm.json.",
            "When the sentence names Rust LSTM with t-route, use realization_rust_lstm_troute.json.",
            "When the sentence names Python LSTM, use realization_python_lstm_troute.json.",
            "When the sentence names SLOTH and t-route without CFE, PET, or Noah-OWP, use realization_sloth_troute.json.",
            "When the sentence says not to run or not to simulate, leave realization empty.",
            "When the sentence asks to run or simulate and does not name a model, set realization to realization_sloth_nom_cfe_pet_troute.json.",
            "That choice is CFE, PET, Noah-OWP, and t-route. Say in the note that no model was named and that stack was chosen.",
            "outputDir is a folder path or an empty string. Do not invent a folder name.",
            "note is one short sentence about what you filled.",
            "Do not invent a gage or a date. Do not set log paths, result paths, or the live log.",
        ]
    )
