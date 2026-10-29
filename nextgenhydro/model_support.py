import re

from .settings import DATASTREAM_ROOT

DOC = DATASTREAM_ROOT / "docs" / "NGEN_MODELS.md"


def model_catalog() -> tuple[set[str], set[str]]:
    if not DOC.is_file():
        return set(), set()
    supported: set[str] = set()
    later: set[str] = set()
    section = ""
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            title = line.lower()
            if "available via" in title:
                section = "supported"
            elif "coming soon" in title:
                section = "later"
            else:
                section = ""
            continue
        if not section or not line.strip().startswith("*"):
            continue
        match = re.search(r"\[([^\]]+)\]", line)
        if not match:
            continue
        (supported if section == "supported" else later).add(match.group(1))
    return supported, later


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _supported_keys() -> set[str]:
    supported, _later = model_catalog()
    keys = {_norm(name) for name in supported}
    keys.update({"cfe", "pet", "sloth", "noahowp", "noahowpmodular", "troute", "lstm", "lstmrust", "rustlstm", "pythonlstm"})
    return keys


def _appears(sentence: str, name: str) -> bool:
    parts = [re.escape(part) for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    if not parts:
        return False
    return re.search(r"\b" + r"[^A-Za-z0-9]*".join(parts) + r"\b", sentence, re.I) is not None


FRAMEWORK_KEYS = {"nextgen", "ngen", "ngiab", "nextgeninabox", "nextgenhydro", "nextgeninthebox"}


def is_framework_name(name: str) -> bool:
    return _norm(name) in FRAMEWORK_KEYS


def sentence_names_framework(sentence: str) -> bool:
    return re.search(r"\b(?:next[\s-]*gen(?:eration)?|ngen|ngiab)\b", sentence or "", re.I) is not None


def _clean_names(names: list | None) -> list[str]:
    cleaned = []
    for name in names or []:
        if not isinstance(name, str):
            continue
        text = re.sub(r"\s+", " ", name).strip(" .")
        if text and not re.fullmatch(r"\d{7,15}", text):
            cleaned.append(text)
    return cleaned


def catalog_model_names(names: list | None) -> list[str]:
    return [name for name in _clean_names(names) if not is_framework_name(name)]


def unsupported_models(sentence: str, extra: list | None = None) -> list[str]:
    supported = _supported_keys()
    _supported_names, later = model_catalog()
    found = []
    seen = set()
    for name in sorted(later, key=lambda item: sentence.lower().find(item.lower()) if _appears(sentence, item) else 10**9):
        if not _appears(sentence, name):
            continue
        key = _norm(name)
        if key and key not in seen and key not in supported and key not in FRAMEWORK_KEYS:
            seen.add(key)
            found.append(name)
    for name in catalog_model_names(extra):
        key = _norm(name)
        if not key or key in seen or key in supported:
            continue
        seen.add(key)
        found.append(name)
    return found


def unsupported_note(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return f"{names[0]} is a hydrologic model. It is not supported in this repo for now, so this run is not ready."
    if len(names) == 2:
        listed = f"{names[0]} and {names[1]}"
    else:
        listed = ", ".join(names[:-1]) + ", and " + names[-1]
    return f"{listed} are hydrologic models. They are not supported in this repo for now, so this run is not ready."


def check_models(sentence: str, extra: list | None = None) -> dict:
    missing = unsupported_models(sentence, extra)
    if missing:
        return {"ok": False, "unsupported": missing, "message": unsupported_note(missing)}
    kept = _clean_names(extra)
    if kept:
        listed = ", ".join(kept)
        return {"ok": True, "unsupported": [], "message": f"Resolved models: {listed}."}
    return {"ok": True, "unsupported": [], "message": ""}
