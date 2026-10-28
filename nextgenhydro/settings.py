import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _path_setting(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else default.resolve()


DATASTREAM_ROOT = _path_setting("DATASTREAM_ROOT", ROOT.parent / "NexGen" / "datastreamcli")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-5-mini"
NGIAB_PREP_PYTHON = os.environ.get("NGIAB_PREP_PYTHON", "").strip() or "3.12"
