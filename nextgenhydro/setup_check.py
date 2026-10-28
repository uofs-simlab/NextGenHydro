import os
import re
import shutil
import subprocess
from pathlib import Path

from .realizations import REALIZATIONS
from .settings import DATASTREAM_ROOT, NGIAB_PREP_PYTHON

MIN_DATASTREAM = (1, 7, 2)


def _version(text: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def datastream_image_version(root: Path = DATASTREAM_ROOT) -> str:
    override = os.environ.get("DS_TAG", "").strip()
    if override:
        return override
    try:
        text = (root / "versions.yml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'^datastream:\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else ""


def _problem(name: str, message: str, fix: str, blocking: bool = True) -> dict:
    return {"name": name, "message": message, "fix": fix, "blocking": blocking}


def _uv_tools_writable() -> bool:
    base = Path(os.environ.get("UV_TOOL_DIR", "") or Path.home() / ".local" / "share" / "uv" / "tools")
    probe = base
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return os.access(probe, os.W_OK)


def _docker_running() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=8).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


FAILURE_HINTS = [
    (r"Realization start time.*does not match forcing start time|does not match forcing start time", "The realization clock was one hour behind the first National Water Model forcing hour. Refresh, Ask again, then press Run with a new output folder."),
    (r"forcing_medium_range_mem\d|medium_range\.forcing_\d", "DataStreamCLI asked NOAA for ensemble-member medium-range forcing files. NOAA now publishes those hours under forcing_medium_range without a member number. Refresh, Ask again, then press Run with a new output folder."),
    (r"NoSuchKey|does not exist.*nwm\.|nwm\..*does not exist|Could not extract forecast cycle", "Those National Water Model forecast files are not on NOAA's server for that cycle. Refresh, Ask again so the plan uses the shared medium-range forcing files, then press Run with a new output folder."),
    (r"Permission denied.*(?:\.local|uv)|(?:\.local|uv).*Permission denied", "uv could not write to ~/.local. Run: sudo chown -R $(whoami) ~/.local, then press Run again."),
    (r"no interpreter found|requires-python|No solution found when resolving|Failed to build", f"A package for the watershed step could not be installed for this Python version. The app asks uv for Python {NGIAB_PREP_PYTHON}; install it with: uv python install {NGIAB_PREP_PYTHON}"),
    (r"Cannot connect to the Docker daemon|docker daemon is not running|Is the docker daemon running", "Docker is not running. Open Docker Desktop, wait until it is running, then press Run again."),
    (r"Could not resolve host|Temporary failure in name resolution|Network is unreachable|ConnectionError|timed out", "A download failed. Check the internet connection, then press Run again."),
    (r"No space left on device", "The disk is full. Free some space, then press Run again."),
    (r"pigz: (?:command )?not found", "pigz is missing. Install it, for example: brew install pigz"),
    (r"(?:DATA_DIR|data directory|directory).*already exists", "The output folder already exists. Type a new folder name, then press Run again."),
    (r"[Vv]alidat\w*.*(?:fail|error|exited)|(?:fail|error).*[Vv]alidat", "The run stopped at validation. DataStreamCLI images before 1.7.2 fail here when there is no t-route restart file. Use the ngen-app-fixing branch, or start the app with DS_TAG=1.7.2."),
]


def explain_failure(output: str) -> str:
    for pattern, hint in FAILURE_HINTS:
        if re.search(pattern, output or "", re.I):
            return hint
    return ""


def setup_problems(root: Path = DATASTREAM_ROOT, key_loaded: bool = True) -> list[dict]:
    problems = []
    script = root / "scripts" / "datastream"
    if not script.is_file():
        problems.append(_problem(
            "DataStreamCLI",
            f"DataStreamCLI was not found at {root}.",
            "Clone the uofs-simlab fork (branch ngen-app-fixing) to that folder, or start the app with DATASTREAM_ROOT=/path/to/datastreamcli.",
        ))
    else:
        missing = [item["id"] for item in REALIZATIONS if not (root / "configs" / "ngen" / item["id"]).is_file()]
        if missing:
            problems.append(_problem(
                "Realizations",
                f"These realization files are missing from {root / 'configs' / 'ngen'}: {', '.join(missing)}.",
                "Check out the ngen-app-fixing branch of the uofs-simlab DataStreamCLI fork.",
            ))
        if not (root / "docs" / "NGEN_MODELS.md").is_file():
            problems.append(_problem(
                "Model list",
                "docs/NGEN_MODELS.md is missing, so the app cannot check which models DataStreamCLI supports.",
                "Check out the ngen-app-fixing branch of the uofs-simlab DataStreamCLI fork.",
            ))
        tag = datastream_image_version(root)
        found = _version(tag) if tag else None
        if found is None:
            problems.append(_problem(
                "DataStreamCLI version",
                "versions.yml does not name a datastream image version.",
                "Check out the ngen-app-fixing branch of the uofs-simlab DataStreamCLI fork.",
            ))
        elif found < MIN_DATASTREAM:
            needed = ".".join(str(part) for part in MIN_DATASTREAM)
            problems.append(_problem(
                "DataStreamCLI version",
                f"DataStreamCLI pins the datastream image {tag}. Runs stop at validation on versions before {needed}.",
                f"Check out the ngen-app-fixing branch, or start the app with DS_TAG={needed}.",
            ))
    if shutil.which("docker") is None:
        problems.append(_problem("Docker", "Docker is not installed.", "Install Docker Desktop and start it before Run."))
    elif not _docker_running():
        problems.append(_problem("Docker", "Docker is installed but not running.", "Open Docker Desktop and wait until it says it is running, then press Run."))
    if shutil.which("uvx") is None:
        problems.append(_problem("uv", "uvx was not found, so the watershed step cannot run.", "Install uv from https://docs.astral.sh/uv/getting-started/installation/ and confirm with uvx --version."))
    elif not _uv_tools_writable():
        problems.append(_problem("uv", "uv cannot write to its tools folder in ~/.local/share/uv.", "Run: sudo chown -R $(whoami) ~/.local"))
    if shutil.which("pigz") is None:
        problems.append(_problem("pigz", "pigz was not found. DataStreamCLI uses it to pack the model configs.", "Install it, for example: brew install pigz"))
    if not key_loaded:
        problems.append(_problem(
            "OpenAI key",
            "No OpenAI key was found. Ask uses the local reader, which understands fewer sentences.",
            "Copy .openai-key.local.example to .openai-key.local and put your key in it, then restart the app.",
            blocking=False,
        ))
    return problems
