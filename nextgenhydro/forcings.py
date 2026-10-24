import re

FORCINGS = [
    {"id": "NWM_RETRO_V3", "label": "National Water Model v3 retrospective"},
    {"id": "NWM_RETRO_V2", "label": "National Water Model v2 retrospective"},
    {"id": "NWM_OPERATIONAL_V3", "label": "National Water Model v3 operational"},
    {"id": "NOMADS_OPERATIONAL", "label": "NOMADS operational"},
    {"id": "NWM_V3_SHORT_RANGE", "label": "National Water Model v3 short range"},
    {"id": "NWM_V3_MEDIUM_RANGE", "label": "National Water Model v3 medium range"},
    {"id": "NWM_V3_ANALYSIS_ASSIM", "label": "National Water Model v3 analysis and assimilation"},
]

FORCING_IDS = {item["id"] for item in FORCINGS}

SHORT_RANGE_CYCLE = re.compile(r"NWM_V3_SHORT_RANGE_(0\d|1\d|2[0-3])")
MEDIUM_RANGE_CYCLE = re.compile(r"NWM_V3_MEDIUM_RANGE_(00|06|12|18)_([1-7])")


def forecast_kind(value: str) -> str:
    value = value or ""
    if value == "NWM_V3_SHORT_RANGE" or SHORT_RANGE_CYCLE.fullmatch(value):
        return "short"
    if value == "NWM_V3_MEDIUM_RANGE" or MEDIUM_RANGE_CYCLE.fullmatch(value):
        return "medium"
    return ""


def has_forecast_cycle(value: str) -> bool:
    return bool(SHORT_RANGE_CYCLE.fullmatch(value or "") or MEDIUM_RANGE_CYCLE.fullmatch(value or ""))


def is_forcing_id(value: str) -> bool:
    return value in FORCING_IDS or has_forecast_cycle(value)
