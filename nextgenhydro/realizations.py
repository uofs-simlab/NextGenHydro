REALIZATIONS = [
    {"id": "realization_sloth_nom_cfe_pet_troute.json", "label": "CFE, PET, Noah-OWP, and t-route"},
    {"id": "realization_sloth_nom_cfe_pet.json", "label": "CFE, PET, and Noah-OWP"},
    {"id": "realization_sloth_troute.json", "label": "SLOTH and t-route"},
    {"id": "realization_rust_lstm_troute.json", "label": "Rust LSTM and t-route"},
    {"id": "realization_rust_lstm.json", "label": "Rust LSTM"},
    {"id": "realization_python_lstm_troute.json", "label": "Python LSTM and t-route"},
]

REALIZATION_IDS = {item["id"] for item in REALIZATIONS}
DEFAULT_REALIZATION = "realization_sloth_nom_cfe_pet_troute.json"


def is_realization_id(value: str) -> bool:
    return value in REALIZATION_IDS


def output_dir_for(_gage: str, output_dir: str) -> str:
    return output_dir.strip()


def _under_output(output_dir: str, child: str) -> str:
    output = output_dir_for("", output_dir).strip()
    if not output:
        return ""
    base = output.rstrip("/\\")
    if not base:
        return f"/{child}"
    return f"{base}/{child}"


def log_path_for(_gage: str, output_dir: str) -> str:
    return _under_output(output_dir, "datastream-metadata/datastream_steps.txt")


def result_path_for(_gage: str, output_dir: str) -> str:
    return _under_output(output_dir, "ngen-run/outputs")


def live_log_path_for(_gage: str, output_dir: str) -> str:
    return _under_output(output_dir, "logs/nextgenhydro.log")


def realization_label(realization_id: str) -> str:
    return next((item["label"] for item in REALIZATIONS if item["id"] == realization_id), realization_id)


def excludes_routing(text: str) -> bool:
    import re

    target = r"(?:t-route|troute|routing)\b"
    return re.search(
        rf"\b(?:without|not using|do not use|don't use|dont use)\b(?:\s+[\w-]+){{0,6}}?\s+{target}|\bno\s+{target}",
        text,
        re.I,
    ) is not None


def read_realization(text: str) -> str:
    value = text.lower()
    import re

    troute = re.search(r"\b(?:t-route|troute|routing)\b", value) is not None and not excludes_routing(value)
    lstm = re.search(r"\blstm\b", value) is not None
    rust = re.search(r"\brust\b", value) is not None
    python = re.search(r"\bpython\b", value) is not None
    noah = re.search(r"\bnoah(?:\s*[- ]\s*owp|owp)\b", value) is not None
    cfe = re.search(r"\bcfe\b", value) is not None
    pet = re.search(r"\bpet\b", value) is not None
    sloth = re.search(r"\bsloth\b", value) is not None
    if lstm and python:
        return "realization_python_lstm_troute.json"
    if lstm and (rust or troute) and troute:
        return "realization_rust_lstm_troute.json"
    if lstm and rust:
        return "realization_rust_lstm.json"
    if lstm:
        return "realization_rust_lstm.json"
    if sloth and troute and not noah and not cfe and not pet:
        return "realization_sloth_troute.json"
    if (noah or cfe or pet) and troute:
        return "realization_sloth_nom_cfe_pet_troute.json"
    if noah or cfe or pet:
        return "realization_sloth_nom_cfe_pet.json"
    return ""
