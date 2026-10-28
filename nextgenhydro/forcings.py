import re

FORCINGS = [
    {"id": "NWM_RETRO_V3", "label": "National Water Model v3 retrospective (Feb 1979 to Jan 2023)"},
    {"id": "NWM_RETRO_V2", "label": "National Water Model v2 retrospective (Feb 1979 to Dec 2019)"},
    {"id": "NWM_OPERATIONAL_V3", "label": "National Water Model v3 operational"},
    {"id": "NOMADS_OPERATIONAL", "label": "NOMADS operational"},
    {"id": "NWM_V3_SHORT_RANGE", "label": "National Water Model v3 short range"},
    {"id": "NWM_V3_MEDIUM_RANGE", "label": "National Water Model v3 medium range"},
    {"id": "NWM_V3_ANALYSIS_ASSIM", "label": "National Water Model v3 analysis and assimilation"},
]

FORCING_IDS = {item["id"] for item in FORCINGS}

# First and last hourly forcing files in the public NOAA buckets.
RETROSPECTIVE_COVERAGE = {
    "NWM_RETRO_V3": ("1979-02-01T00:00", "2023-01-31T23:00"),
    "NWM_RETRO_V2": ("1979-02-01T00:00", "2019-12-31T23:00"),
}


def coverage_problem(forcing: str, start: str, end: str) -> str:
    span = RETROSPECTIVE_COVERAGE.get(forcing)
    if not span or not start or not end:
        return ""
    first, last = span
    if start >= first and end <= last:
        return ""
    name = "v3" if forcing == "NWM_RETRO_V3" else "v2"
    return (
        f"NWM {name} retrospective forcing covers {first.replace('T', ' ')} to {last.replace('T', ' ')} UTC. "
        "Move the dates inside that range or choose another forcing."
    )

SHORT_RANGE_CYCLE = re.compile(r"NWM_V3_SHORT_RANGE_(0\d|1\d|2[0-3])")
MEDIUM_RANGE_CYCLE = re.compile(r"NWM_V3_MEDIUM_RANGE_(00|06|12|18)_([0-7])")


def forecast_kind(value: str) -> str:
    value = value or ""
    if value == "NWM_V3_SHORT_RANGE" or SHORT_RANGE_CYCLE.fullmatch(value):
        return "short"
    if value == "NWM_V3_MEDIUM_RANGE" or MEDIUM_RANGE_CYCLE.fullmatch(value):
        return "medium"
    return ""


def has_forecast_cycle(value: str) -> bool:
    return bool(SHORT_RANGE_CYCLE.fullmatch(value or "") or MEDIUM_RANGE_CYCLE.fullmatch(value or ""))


def canonical_forecast_forcing(value: str) -> str:
    match = MEDIUM_RANGE_CYCLE.fullmatch(value or "")
    if match:
        return f"NWM_V3_MEDIUM_RANGE_{match.group(1)}_0"
    return value or ""


def is_forcing_id(value: str) -> bool:
    return value in FORCING_IDS or has_forecast_cycle(value)
