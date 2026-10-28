import calendar
import re
from datetime import datetime, timedelta, timezone

from .forcings import FORCINGS, is_forcing_id

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))

EMPTY_REQUEST = {"gage": "", "start": "", "end": "", "forcing": ""}


def _pad(value: int) -> str:
    return f"{value:02d}"


def to_iso(year: int, month: int, day: int, hour: int, minute: int) -> str | None:
    if year < 1970 or year > 2100:
        return None
    if month < 1 or month > 12 or day < 1 or hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    if day > calendar.monthrange(year, month)[1]:
        return None
    return f"{year}-{_pad(month)}-{_pad(day)}T{_pad(hour)}:{_pad(minute)}"


def _hour_from_clock(hour_text: str, meridiem: str | None) -> int | None:
    hour = int(hour_text)
    if not meridiem:
        return hour
    marker = meridiem.lower()
    if marker == "pm" and hour < 12:
        hour += 12
    if marker == "am" and hour == 12:
        hour = 0
    if hour > 23:
        return None
    return hour


def _push_date(found: list[dict], index: int, length: int, iso: str | None) -> None:
    if not iso:
        return
    if any(index < item["index"] + item["length"] and index + length > item["index"] for item in found):
        return
    found.append({"index": index, "length": length, "iso": iso})


def _apply_clock(text: str, found: dict) -> None:
    after = text[found["index"] + found["length"] : found["index"] + found["length"] + 24]
    clock = re.match(r"^\s*(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", after, re.I)
    if not clock:
        return
    hour = _hour_from_clock(clock.group(1), clock.group(3))
    if hour is None:
        return
    minute = int(clock.group(2)) if clock.group(2) else 0
    parts = re.match(r"^(\d{4})-(\d{2})-(\d{2})", found["iso"])
    if not parts:
        return
    iso = to_iso(int(parts.group(1)), int(parts.group(2)), int(parts.group(3)), hour, minute)
    if not iso:
        return
    found["iso"] = iso
    found["length"] += len(clock.group(0))


def find_dates(text: str) -> list[dict]:
    found: list[dict] = []
    for match in re.finditer(r"\b(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\b", text):
        _push_date(
            found,
            match.start(),
            len(match.group(0)),
            to_iso(int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))),
        )
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?\b", text):
        _push_date(
            found,
            match.start(),
            len(match.group(0)),
            to_iso(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4) or 0),
                int(match.group(5) or 0),
            ),
        )
    for match in re.finditer(r"\b(20\d{2})/(\d{1,2})/(\d{1,2})\b", text):
        _push_date(
            found,
            match.start(),
            len(match.group(0)),
            to_iso(int(match.group(1)), int(match.group(2)), int(match.group(3)), 0, 0),
        )
    for match in re.finditer(r"\b(20\d{2})[/\\-](\d{2})(\d{2})\b", text):
        _push_date(
            found,
            match.start(),
            len(match.group(0)),
            to_iso(int(match.group(1)), int(match.group(2)), int(match.group(3)), 0, 0),
        )
    for match in re.finditer(rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b", text, re.I):
        month = MONTHS[match.group(2).lower()]
        _push_date(found, match.start(), len(match.group(0)), to_iso(int(match.group(3)), month, int(match.group(1)), 0, 0))
    for match in re.finditer(rf"\b({MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", text, re.I):
        month = MONTHS[match.group(1).lower()]
        _push_date(found, match.start(), len(match.group(0)), to_iso(int(match.group(3)), month, int(match.group(2)), 0, 0))
    same_month = re.compile(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})\s*[-–—]\s*(\d{{1,2}}),?\s+(20\d{{2}})\b",
        re.I,
    )
    for match in same_month.finditer(text):
        month = MONTHS[match.group(1).lower()]
        year = int(match.group(4))
        lead = re.match(rf"(?:{MONTH_PATTERN})\s+\d{{1,2}}", match.group(0), re.I)
        tail = re.search(r"\d{1,2},?\s+20\d{2}$", match.group(0))
        _push_date(
            found,
            match.start(),
            len(lead.group(0)) if lead else len(match.group(1)),
            to_iso(year, month, int(match.group(2)), 0, 0),
        )
        if tail:
            _push_date(
                found,
                match.start() + tail.start(),
                len(match.group(0)) - tail.start(),
                to_iso(year, month, int(match.group(3)), 0, 0),
            )
    for match in re.finditer(rf"\b(20\d{{2}})[/\\-]({MONTH_PATTERN}|\d{{1,2}})[/\\-](\d{{1,2}})\b", text, re.I):
        month = MONTHS.get(match.group(2).lower(), int(match.group(2)) if match.group(2).isdigit() else 0)
        _push_date(found, match.start(), len(match.group(0)), to_iso(int(match.group(1)), month, int(match.group(3)), 0, 0))
    found.sort(key=lambda item: item["index"])
    for date in found:
        _apply_clock(text, date)
    return found


def _role_for(text: str, date: dict) -> str:
    before = text[max(0, date["index"] - 28) : date["index"]].lower()
    if re.search(r"\b(?:from|starting|start)\b", before):
        return "start"
    if re.search(r"\b(?:through|until|to)\b", before):
        return "end"
    return ""


def _mask_dates(text: str, dates: list[dict]) -> str:
    chars = list(text)
    for date in dates:
        for index in range(date["index"], min(date["index"] + date["length"], len(chars))):
            chars[index] = " "
    return "".join(chars)


def _read_gage(text: str, dates: list[dict]) -> str:
    masked = _mask_dates(text, dates)
    labeled = re.search(r"\b(?:usgs|gage|gauge|site)\s*#?\s*(\d{7,15})\b", masked, re.I)
    if labeled:
        return labeled.group(1)
    bare = re.search(r"\b(\d{7,15})\b", masked)
    return bare.group(1) if bare else ""


def _add_duration(iso: str, amount: int, unit: str) -> str:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$", iso)
    if not match:
        return iso
    date = datetime(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
        int(match.group(5)),
        tzinfo=timezone.utc,
    )
    name = unit.lower()
    if name.startswith("hour") or name == "hr":
        date += timedelta(hours=amount)
    elif name.startswith("week"):
        date += timedelta(days=amount * 7)
    else:
        date += timedelta(days=amount)
    return to_iso(date.year, date.month, date.day, date.hour, date.minute) or iso


def read_forcing(text: str) -> str:
    for item in FORCINGS:
        if re.search(rf"\b{item['id']}\b", text, re.I):
            return item["id"]
    value = text.lower()
    if re.search(r"\b(?:retrospective|retro)\s+v(?:ersion\s*)?2\b", value) or re.search(r"\bv2\s+retrospective\b", value):
        return "NWM_RETRO_V2"
    if re.search(r"\b(?:retrospective|retro)\s+v(?:ersion\s*)?3\b", value) or re.search(r"\baorc\b", value):
        return "NWM_RETRO_V3"
    if re.search(r"\bshort[\s-]*range\b", value):
        return "NWM_V3_SHORT_RANGE"
    if re.search(r"\bmedium[\s-]*range\b", value):
        return "NWM_V3_MEDIUM_RANGE"
    if re.search(r"\banalysis(?:\s+and|\s*&\s*|\s+)assimilation\b", value):
        return "NWM_V3_ANALYSIS_ASSIM"
    if re.search(r"\b(?:retrospective|retro)\b", value):
        return "NWM_RETRO_V3"
    if re.search(r"\bnomads\b", value):
        return "NOMADS_OPERATIONAL"
    if re.search(r"\boperational\b", value):
        return "NWM_OPERATIONAL_V3"
    return ""


WEEKS = {
    "first": (1, 7),
    "1st": (1, 7),
    "second": (8, 14),
    "2nd": (8, 14),
    "third": (15, 21),
    "3rd": (15, 21),
    "fourth": (22, 28),
    "4th": (22, 28),
}


def _find_week(text: str) -> dict | None:
    match = re.search(
        rf"\b(?:the\s+)?(first|second|third|fourth|1st|2nd|3rd|4th)\s+week\s+of\s+({MONTH_PATTERN}),?\s+(20\d{{2}})\b",
        text,
        re.I,
    )
    if not match:
        return None
    span = WEEKS.get(match.group(1).lower())
    month = MONTHS.get(match.group(2).lower())
    if not span or not month:
        return None
    start = to_iso(int(match.group(3)), month, span[0], 0, 0)
    end = to_iso(int(match.group(3)), month, span[1], 0, 0)
    if not start or not end:
        return None
    return {"start": start, "end": end}


def _find_months(text: str) -> list[dict]:
    found = []
    for match in re.finditer(rf"\b({MONTH_PATTERN})\s+(20\d{{2}})\b", text, re.I):
        month = MONTHS.get(match.group(1).lower())
        if not month:
            continue
        found.append({"year": int(match.group(2)), "month": month})
    return found


MAX_WARMUP_DAYS = 730
_WARMUP_WORD = r"(?:warm[\s-]?up|spin[\s-]?up)"
_WARMUP_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
WARMUP_PATTERN = re.compile(
    rf"\b(\d+)\s*-?\s*(day|week|month|year)s?\s*(?:of\s+)?(?:model\s+)?{_WARMUP_WORD}"
    rf"|\b{_WARMUP_WORD}(?:\s+(?:period|time))?\s*(?:of|for|:)?\s*(\d+)\s*-?\s*(day|week|month|year)s?\b",
    re.I,
)


def read_warmup_days(text: str) -> int:
    match = WARMUP_PATTERN.search(text)
    if not match:
        return 0
    amount = int(match.group(1) or match.group(3))
    unit = (match.group(2) or match.group(4)).lower()
    return min(amount * _WARMUP_UNIT_DAYS[unit], MAX_WARMUP_DAYS)


SEASONS = {
    "spring": (3, 5),
    "summer": (6, 8),
    "fall": (9, 11),
    "autumn": (9, 11),
    "winter": (12, 2),
}


def _month_end(year: int, month: int) -> str:
    return to_iso(year, month, calendar.monthrange(year, month)[1], 0, 0) or ""


def _find_season(text: str) -> dict | None:
    match = re.search(r"\b(spring|summer|fall|autumn|winter)\s+(?:of\s+)?((?:19|20)\d{2})\b", text, re.I)
    if not match:
        return None
    first, last = SEASONS[match.group(1).lower()]
    year = int(match.group(2))
    end_year = year + 1 if first > last else year
    start = to_iso(year, first, 1, 0, 0)
    end = _month_end(end_year, last)
    return {"start": start, "end": end} if start and end else None


def _find_year(text: str) -> dict | None:
    water = re.search(r"\bwater\s+year\s+((?:19|20)\d{2})\b", text, re.I)
    if water:
        year = int(water.group(1))
        start = to_iso(year - 1, 10, 1, 0, 0)
        end = to_iso(year, 9, 30, 0, 0)
        return {"start": start, "end": end} if start and end else None
    match = re.search(r"\b(?:in|for|during|throughout|over|year)\s+((?:19|20)\d{2})\b(?!\s*[-/\\]\s*\d)", text, re.I)
    if not match:
        return None
    year = int(match.group(1))
    start = to_iso(year, 1, 1, 0, 0)
    end = to_iso(year, 12, 31, 0, 0)
    return {"start": start, "end": end} if start and end else None


def parse_request(text: str) -> dict:
    dates = find_dates(text)
    start = ""
    end = ""
    unassigned: list[dict] = []
    for date in dates:
        role = _role_for(text, date)
        if role == "start" and not start:
            start = date["iso"]
        elif role == "end" and not end:
            end = date["iso"]
        else:
            unassigned.append(date)
    if not start and unassigned:
        start = unassigned.pop(0)["iso"]
    if not end and unassigned:
        end = unassigned.pop(0)["iso"]
    duration = re.search(r"\b(\d+)\s*-?\s*(hour|hr|day|week)s?\b", WARMUP_PATTERN.sub(" ", text), re.I)
    if duration and start:
        end = _add_duration(start, int(duration.group(1)), duration.group(2))
    if not start and not end:
        week = _find_week(text)
        if week:
            start = week["start"]
            end = week["end"]
    if not start and not end:
        months = _find_months(text)
        if months:
            first, last = months[0], months[-1]
            start = to_iso(first["year"], first["month"], 1, 0, 0) or ""
            end = to_iso(last["year"], last["month"], calendar.monthrange(last["year"], last["month"])[1], 0, 0) or ""
    for finder in (_find_season, _find_year):
        if start or end:
            break
        span = finder(text)
        if span:
            start = span["start"]
            end = span["end"]
    forcing = read_forcing(text)
    return {
        "gage": _read_gage(text, dates),
        "start": start,
        "end": end,
        "forcing": forcing if is_forcing_id(forcing) or forcing == "" else "",
    }


def to_datastream_time(iso: str) -> str:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$", iso)
    if not match:
        return ""
    return "".join(match.groups())


def align_hourly_time(iso: str) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}):(\d{2})$", iso)
    if not match or match.group(2) == "00":
        return iso
    return f"{match.group(1)}:00"


def hourly_clock_note(start: str, end: str) -> str:
    next_start = align_hourly_time(start)
    next_end = align_hourly_time(end)
    moved = []
    if next_start != start:
        moved.append(f"start {start.replace('T', ' ')} to {next_start.replace('T', ' ')}")
    if next_end != end:
        moved.append(f"end {end.replace('T', ' ')} to {next_end.replace('T', ' ')}")
    if not moved:
        return ""
    return (
        "Forcing is hourly, so "
        + " and ".join(moved)
        + " before DataStreamCLI starts. The realization clock then matches the forcing hour."
    )


def merge_request(current: dict, parsed: dict) -> dict:
    return {
        "gage": parsed.get("gage") or current.get("gage", ""),
        "start": parsed.get("start") or current.get("start", ""),
        "end": parsed.get("end") or current.get("end", ""),
        "forcing": parsed.get("forcing") or current.get("forcing", ""),
    }
