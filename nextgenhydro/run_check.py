import re
from datetime import datetime, timezone

from .agent import is_gage_id, is_iso_date_time, is_safe_output_dir
from .forcings import RETROSPECTIVE_COVERAGE, coverage_problem, forecast_kind, has_forecast_cycle, is_forcing_id
from .datastream_command import warmup_days, warmup_start
from .parse_request import MAX_WARMUP_DAYS, align_hourly_time
from .realizations import is_realization_id


def run_problems(body: dict, now=None) -> list[dict]:
    problems = []

    def add(field: str, message: str) -> None:
        problems.append({"field": field, "message": message})

    gage = str(body.get("gage") or "").strip()
    if not gage:
        add("gage", "Type a USGS gauge number, or ask for a place and pick a station on the map.")
    elif not is_gage_id(gage):
        add("gage", f"The gauge must be 7 to 15 digits, such as 01646500. {gage!r} is not a gauge number.")
    start = align_hourly_time(str(body.get("start") or ""))
    end = align_hourly_time(str(body.get("end") or ""))
    if not start:
        add("start", "Choose a start date.")
    elif not is_iso_date_time(start):
        add("start", "The start is not a real date and time.")
    if not end:
        add("end", "Choose an end date.")
    elif not is_iso_date_time(end):
        add("end", "The end is not a real date and time.")
    if start and end and is_iso_date_time(start) and is_iso_date_time(end) and end <= start:
        add("end", "The end must be after the start.")
    forcing = str(body.get("forcing") or "")
    if not forcing:
        add("forcing", "Choose a forcing. Retrospective covers past dates, and short or medium range covers forecasts.")
    elif not is_forcing_id(forcing):
        add("forcing", "That forcing is not one DataStreamCLI offers.")
    elif forecast_kind(forcing) and is_iso_date_time(end):
        try:
            ended = datetime.strptime(end, "%Y-%m-%dT%H:%M")
        except ValueError:
            ended = None
        clock = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
        if ended and ended <= clock:
            add("end", "Those dates are already in the past. A forecast covers upcoming hours, so this time range is not for forecasting.")
        elif not has_forecast_cycle(forcing):
            add("forcing", "A forecast forcing needs its issue cycle. Ask the agent for the forecast so it picks the newest cycle.")
    elif forecast_kind(forcing) and not has_forecast_cycle(forcing):
        add("forcing", "A forecast forcing needs its issue cycle. Ask the agent for the forecast so it picks the newest cycle.")
    elif is_iso_date_time(start) and is_iso_date_time(end) and end > start:
        first = warmup_start(start, warmup_days(body.get("warmupDays")))
        outside = coverage_problem(forcing, first, end)
        if outside:
            archive_start = RETROSPECTIVE_COVERAGE[forcing][0]
            if first >= archive_start:
                add("end", outside)
            elif start >= archive_start:
                add("warmup", f"With the warm-up the run starts at {first.replace('T', ' ')}. {outside}")
            else:
                add("start", outside)
    raw_warmup = body.get("warmupDays")
    if raw_warmup not in (None, "", 0, "0") and (not str(raw_warmup).isdigit() or int(raw_warmup) > MAX_WARMUP_DAYS):
        add("warmup", f"Warm-up must be a whole number of days from 0 to {MAX_WARMUP_DAYS}.")
    elif warmup_days(raw_warmup) and forecast_kind(forcing):
        add("warmup", "Warm-up works with retrospective forcing. Set it to 0 for a forecast.")
    if not is_realization_id(str(body.get("realization") or "")):
        add("realization", "Choose a realization.")
    output_dir = str(body.get("outputDir") or "").strip()
    if not output_dir:
        add("output", "Type an output folder, such as ./data/my-run.")
    elif not is_safe_output_dir(output_dir) or len(output_dir) > 500 or ".." in re.split(r"[/\\]", output_dir):
        add("output", "The output folder must be a plain path inside datastreamcli, without .. or line breaks.")
    if body.get("evaluate") is True:
        realization = str(body.get("realization") or "")
        if is_realization_id(realization) and "troute" not in realization:
            add("evaluate", "Evaluation reads the t-route streamflow, so choose a realization with t-route.")
        if forecast_kind(forcing):
            add("evaluate", "Evaluation compares with past USGS observations, so it works with retrospective dates.")
        if body.get("action") == "dry run":
            add("evaluate", "A dry run writes no streamflow to evaluate. Turn off evaluation or run for real.")
    if body.get("action") == "do not run":
        add("action", "The plan says this run is not ready. Read the note, then fix the form or ask again.")
    return problems


def problems_text(problems: list[dict]) -> str:
    return " ".join(item["message"] for item in problems)
