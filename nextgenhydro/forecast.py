from datetime import datetime, timedelta, timezone

from .forcings import forecast_kind

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
    return f"NWM_V3_MEDIUM_RANGE_{cycle.hour:02d}_1"


def plan_forecast(forcing: str, start: str, end: str, now: datetime | None = None) -> dict | None:
    kind = forecast_kind(forcing)
    if not kind:
        return None
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    asked_start, asked_end = _parse(start), _parse(end)
    asked_hours = (asked_end - asked_start).total_seconds() / 3600 if asked_start and asked_end else 0
    switched = kind == "short" and asked_hours > PRODUCTS["short"]["hours"]
    if switched:
        kind = "medium"
    product = PRODUCTS[kind]
    newest = _floor(now - timedelta(hours=product["ready_after"]), product["every"])
    cycle = min(_floor(asked_start, product["every"]), newest) if asked_start else newest
    last_hour = cycle + timedelta(hours=product["hours"] - 1)
    forcing_id = _forcing_id(kind, cycle)
    issued = f"{cycle:%Y-%m-%d} {cycle:%H}Z"
    member = ", member 1" if kind == "medium" else ""
    lead = f"This is a forecast, so {product['label']} was chosen"
    if switched:
        lead = f"This is a forecast longer than 18 hours, so {product['label']} was chosen in place of short range"
    span = f"It runs {product['hours']} hours from {_iso(cycle).replace('T', ' ')} to {_iso(last_hour).replace('T', ' ')} UTC"
    if now - cycle > timedelta(days=KEPT_DAYS):
        return {
            "ok": False,
            "forcing": forcing_id,
            "start": start,
            "end": end,
            "message": f"{lead}, but forecast files are kept for about {KEPT_DAYS} days, so the forecast issued {issued} is no longer available and this run is not ready.",
        }
    if asked_end and asked_end > last_hour:
        return {
            "ok": False,
            "forcing": forcing_id,
            "start": _iso(cycle),
            "end": end,
            "message": f"{lead}: the forecast issued {issued}{member}. {span}, which ends before the requested end {end.replace('T', ' ')}, so this run is not ready.",
        }
    covers = f", which covers the requested end {end.replace('T', ' ')}" if asked_end else ""
    return {
        "ok": True,
        "forcing": forcing_id,
        "start": _iso(cycle),
        "end": end or _iso(last_hour),
        "message": f"{lead}: the forecast issued {issued}{member}. {span}{covers}. Start is the forecast issue time.",
    }
