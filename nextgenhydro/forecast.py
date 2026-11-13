import re
from datetime import datetime, timedelta, timezone

from .forcings import forecast_kind
from .parse_request import named_run_hours

LIVE_FORECAST_FORCINGS = {"NOMADS_OPERATIONAL", "NWM_OPERATIONAL_V3"}

PRODUCTS = {
    "short": {"hours": 18, "every": 1, "ready_after": 2, "label": "National Water Model v3 short range"},
    "medium": {"hours": 240, "every": 6, "ready_after": 6, "label": "National Water Model v3 medium range"},
}
KEPT_DAYS = 30


def _parse(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


def _floor(moment: datetime, every: int) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0, hour=moment.hour - moment.hour % every)


def _forcing_id(kind: str, cycle: datetime) -> str:
    if kind == "short":
        return f"NWM_V3_SHORT_RANGE_{cycle.hour:02d}"
    return f"NWM_V3_MEDIUM_RANGE_{cycle.hour:02d}_0"


def weather_dataset_note(sentence: str) -> str:
    text = sentence or ""
    hrrr = bool(re.search(r"\bhrrr\b", text, re.I))
    gfs = bool(re.search(r"\bgfs\b", text, re.I))
    nomads = bool(re.search(r"\bnomads\b", text, re.I))
    if hrrr:
        return (
            "HRRR (High-Resolution Rapid Refresh) is the NOAA weather forecast that drives "
            "National Water Model v3 short range. DataStreamCLI does not download raw HRRR files; "
            "NWM short-range forcing is the compatible NextGen dataset and is available."
        )
    if gfs:
        return (
            "GFS is the NOAA weather forecast that drives National Water Model v3 medium range. "
            "DataStreamCLI does not download raw GFS files; NWM medium-range forcing is the compatible NextGen dataset."
        )
    if nomads:
        return (
            "NOMADS serves National Water Model forecast files. This run uses NWM forecast forcing "
            "rather than NOMADS_OPERATIONAL, which skips the cycle and the 01:00 realization clock."
        )
    return ""


def forcing_from_live_weather(sentence: str, forcing: str, start: str = "", end: str = "") -> str:
    named = forcing or ""
    text = sentence or ""
    hrrr = bool(re.search(r"\bhrrr\b", text, re.I))
    gfs = bool(re.search(r"\bgfs\b", text, re.I))
    nomads = named == "NOMADS_OPERATIONAL" or bool(re.search(r"\bnomads\b", text, re.I))
    operational = named == "NWM_OPERATIONAL_V3"
    forecast = bool(re.search(r"\bforecast", text, re.I))
    if hrrr:
        return "NWM_V3_SHORT_RANGE"
    if gfs:
        return "NWM_V3_MEDIUM_RANGE"
    if not forecast or not (nomads or operational or named in LIVE_FORECAST_FORCINGS):
        return named
    asked_start, asked_end = _parse(start), _parse(end)
    hours = (asked_end - asked_start).total_seconds() / 3600 if asked_start and asked_end else 0
    if 0 < hours <= PRODUCTS["short"]["hours"]:
        return "NWM_V3_SHORT_RANGE"
    return "NWM_V3_MEDIUM_RANGE"


def plan_forecast(forcing: str, start: str, end: str, now: datetime | None = None, sentence: str = "") -> dict | None:
    kind = forecast_kind(forcing)
    if not kind:
        return None
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    asked_start, asked_end = _parse(start), _parse(end)
    if asked_end and asked_end <= now:
        bare = "NWM_V3_SHORT_RANGE" if kind == "short" else "NWM_V3_MEDIUM_RANGE"
        return {
            "ok": False,
            "forcing": bare,
            "start": start,
            "end": end,
            "message": "Those dates are already in the past. A forecast covers upcoming hours, so this time range is not for forecasting and this run is not ready.",
        }
    asked_hours = (asked_end - asked_start).total_seconds() / 3600 if asked_start and asked_end else 0
    hrrr = bool(re.search(r"\bhrrr\b", sentence or "", re.I))
    switched = kind == "short" and asked_hours > PRODUCTS["short"]["hours"] and not hrrr
    if switched:
        kind = "medium"
    product = PRODUCTS[kind]
    newest = _floor(now - timedelta(hours=product["ready_after"]), product["every"])
    cycle = newest
    last_hour = cycle + timedelta(hours=product["hours"] - 1)
    forcing_id = _forcing_id(kind, cycle)
    issued = f"{cycle:%Y-%m-%d} {cycle:%H}Z"
    lead = f"This is a forecast, so {product['label']} was chosen"
    if switched:
        lead = f"This is a forecast longer than 18 hours, so {product['label']} was chosen in place of short range"
    span = f"The product covers {product['hours']} hours from {_iso(cycle).replace('T', ' ')} to {_iso(last_hour).replace('T', ' ')} UTC"
    if asked_start and asked_start > last_hour:
        bare = "NWM_V3_SHORT_RANGE" if kind == "short" else "NWM_V3_MEDIUM_RANGE"
        return {
            "ok": False,
            "forcing": bare,
            "start": start,
            "end": end,
            "message": (
                f"{lead}. The newest forecast runs {product['hours']} hours from {_iso(cycle).replace('T', ' ')} "
                f"to {_iso(last_hour).replace('T', ' ')} UTC, which ends before the requested start {start.replace('T', ' ')}, "
                "so this run is not ready."
            ),
        }
    if now - cycle > timedelta(days=KEPT_DAYS):
        return {
            "ok": False,
            "forcing": forcing_id,
            "start": start,
            "end": end,
            "message": f"{lead}, but forecast files are kept for about {KEPT_DAYS} days, so the forecast issued {issued} is no longer available and this run is not ready.",
        }
    named_hours = named_run_hours(sentence)
    from_named = cycle + timedelta(hours=named_hours) if named_hours else None
    if from_named and from_named > last_hour:
        from_named = None
    run_end = asked_end
    if from_named:
        asked_from_cycle = (asked_end - cycle).total_seconds() / 3600 if asked_end else None
        longer_than_named = asked_from_cycle is None or asked_from_cycle > named_hours + 12
        if longer_than_named or from_named > asked_end:
            run_end = from_named
    if asked_end and asked_end > last_hour and not (run_end and run_end <= last_hour):
        return {
            "ok": False,
            "forcing": forcing_id,
            "start": _iso(cycle),
            "end": end,
            "message": f"{lead}: the forecast issued {issued}. {span}, which ends before the requested end {end.replace('T', ' ')}, so this run is not ready.",
        }
    if not run_end:
        run_end = last_hour
    covers = f", which covers the requested end {_iso(run_end).replace('T', ' ')}" if asked_end or named_hours else ""
    trim = ""
    if run_end < last_hour:
        trim = " This run downloads forecast hours through that end, not the unused later hours."
    return {
        "ok": True,
        "forcing": forcing_id,
        "start": _iso(cycle),
        "end": _iso(run_end),
        "message": f"{lead}: the newest forecast issued {issued}. {span}{covers}.{trim} Start is the forecast issue time.",
    }
