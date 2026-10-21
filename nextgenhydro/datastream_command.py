import re

from .parse_request import align_hourly_time, hourly_clock_note, to_datastream_time
from .realizations import output_dir_for
from .watershed import watershed_geopackage


def _shell_arg(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def datastream_command(request: dict, options: dict) -> dict | None:
    start_iso = align_hourly_time(request.get("start", ""))
    end_iso = align_hourly_time(request.get("end", ""))
    start = to_datastream_time(start_iso)
    end = to_datastream_time(end_iso)
    output_dir = output_dir_for(request.get("gage", ""), options.get("outputDir", ""))
    if not request.get("gage") or not start or not end or not output_dir:
        return None
    argv = ["-s", start, "-e", end]
    if request.get("forcing"):
        argv.extend(["-C", request["forcing"]])
    argv.extend(["-d", output_dir])
    argv.extend(["-g", watershed_geopackage(request["gage"])])
    argv.extend(["-R", f"./configs/ngen/{options.get('realization', '')}"])
    try:
        nprocs = int(options.get("nprocs", 4))
    except (TypeError, ValueError):
        nprocs = 4
    nprocs = 4 if nprocs < 1 else min(nprocs, 256)
    argv.extend(["-n", str(nprocs)])
    dry_run = options.get("action") == "dry run"
    if dry_run:
        argv.extend(["-y", "True"])
    if options.get("logging") == "verbose":
        argv.extend(["-V", "True"])
    lines = ["./scripts/datastream \\"]
    for index in range(0, len(argv), 2):
        flag = argv[index]
        value = argv[index + 1] if index + 1 < len(argv) else ""
        last = index + 2 >= len(argv)
        lines.append(f"  {flag} {_shell_arg(value)}{'' if last else ' \\'}")
    dates_ok = end_iso > start_iso
    ready = dates_ok and request.get("forcing", "") != ""
    clock_note = hourly_clock_note(request.get("start", ""), request.get("end", ""))
    note = "Run starts this command in the datastreamcli folder. The output folder must be a new name."
    if not dates_ok:
        note = "The end is not after the start, so this command is not ready."
    elif not request.get("forcing"):
        note = "Forcing is still open, so this command is not ready."
    else:
        note = "Run builds this watershed with NGIAB Data Preprocess when the file is missing, then starts this command in the datastreamcli folder. Forcing stays with DataStreamCLI."
        if dry_run:
            note = "This is a dry run. DataStreamCLI starts with -y True, writes the setup, and skips forcing generation, BMI configuration, validation, and the NextGen execution."
    if clock_note:
        note = f"{note} {clock_note}"
    return {"text": "\n".join(lines), "argv": argv, "ready": ready, "note": note}
