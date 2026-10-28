import csv
import json
import math
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from .site_name import _fetch
from .watershed import resolve_watershed_geopackage

CFS_TO_CMS = 0.028316846592


def _hour(text: str) -> str | None:
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "").replace(" ", "T")[:19])
    except ValueError:
        return None
    return stamp.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def outlet_nexus(gage: str) -> str:
    gpkg = resolve_watershed_geopackage(gage, str(Path.home()))
    if not os.path.isfile(gpkg):
        return ""
    connection = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT nex_id FROM hydrolocations WHERE hl_link = ? LIMIT 1",
            (gage,),
        ).fetchone()
        if row and row[0]:
            return str(row[0])
        row = connection.execute(
            'SELECT toid FROM "flowpath-attributes" WHERE gage = ? LIMIT 1',
            (gage,),
        ).fetchone()
        return str(row[0]) if row and row[0] else ""
    except sqlite3.Error:
        return ""
    finally:
        connection.close()


def read_nex_csv(path: Path) -> list[dict]:
    series = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for row in csv.reader(text.splitlines()):
        if len(row) < 3:
            continue
        hour = _hour(row[1].strip())
        try:
            value = float(row[2])
        except ValueError:
            continue
        if hour and math.isfinite(value):
            series.append({"t": hour, "q": value})
    return series


def usgs_observed(gage: str, start: str, end: str) -> list[dict]:
    if not gage or not start or not end:
        return []
    start_day = start[:10]
    end_day = (datetime.fromisoformat(end) + timedelta(days=1)).strftime("%Y-%m-%d") if len(end) >= 10 else end[:10]
    url = (
        "https://waterservices.usgs.gov/nwis/iv/?format=json&sites="
        + quote(gage)
        + f"&startDT={start_day}&endDT={end_day}&parameterCd=00060"
    )
    text = _fetch(url, timeout=20)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    buckets: dict[str, list[float]] = {}
    for series in payload.get("value", {}).get("timeSeries") or []:
        for block in series.get("values") or []:
            for item in block.get("value") or []:
                hour = _hour(str(item.get("dateTime") or ""))
                try:
                    cfs = float(item.get("value"))
                except (TypeError, ValueError):
                    continue
                if hour and math.isfinite(cfs):
                    buckets.setdefault(hour, []).append(cfs * CFS_TO_CMS)
    return [{"t": hour, "q": sum(values) / len(values)} for hour, values in sorted(buckets.items())]


def skill_scores(observed: list[dict], simulated: list[dict], start: str = "") -> dict | None:
    observed_map = {item["t"]: item["q"] for item in observed}
    pairs = []
    for item in simulated:
        if start and item["t"] < start:
            continue
        if item["t"] in observed_map:
            pairs.append((observed_map[item["t"]], item["q"]))
    if len(pairs) < 3:
        return None
    obs = [pair[0] for pair in pairs]
    sim = [pair[1] for pair in pairs]
    n = len(pairs)
    mean_o = sum(obs) / n
    mean_s = sum(sim) / n
    if mean_o == 0:
        return None
    var_o = sum((value - mean_o) ** 2 for value in obs)
    if var_o == 0:
        return None
    nse = 1 - sum((s - o) ** 2 for o, s in pairs) / var_o
    cov = sum((o - mean_o) * (s - mean_s) for o, s in pairs) / n
    std_o = math.sqrt(var_o / n)
    std_s = math.sqrt(sum((value - mean_s) ** 2 for value in sim) / n)
    r = 0 if std_o == 0 or std_s == 0 else cov / (std_o * std_s)
    alpha = 0 if std_o == 0 else std_s / std_o
    beta = mean_s / mean_o
    kge = 1 - math.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
    return {
        "nse": round(nse, 3),
        "kge": round(kge, 3),
        "relativeBias": round(beta - 1, 3),
        "hours": n,
        "source": "NextGen nexus CSV compared with USGS instantaneous discharge.",
    }


def teehr_metrics(root: Path) -> dict | None:
    folder = root / "ngen-run" / "teehr"
    if not folder.is_dir():
        return None
    for path in folder.rglob("metrics.csv"):
        try:
            rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        except OSError:
            continue
        if not rows:
            continue
        row = next((item for item in rows if "ngen" in " ".join(item.values()).lower()), rows[0])
        found = {}
        for key, value in row.items():
            lower = key.lower().replace(" ", "").replace("_", "")
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if "klinggupta" in lower or lower == "kge":
                found["kge"] = round(number, 3)
            elif "nashsutcliffe" in lower or lower == "nse":
                found["nse"] = round(number, 3)
            elif "relativebias" in lower or lower in {"rb", "pbias", "percentbias"}:
                found["relativeBias"] = round(number, 3)
        if found:
            found["source"] = "TEEHR metrics.csv"
            found["hours"] = None
            return found
    return None


def hydrograph(root: Path, gage: str, start: str, end: str) -> dict:
    nexus = outlet_nexus(gage)
    simulated = []
    if nexus:
        simulated = read_nex_csv(root / "ngen-run" / "outputs" / "ngen" / f"{nexus}_output.csv")
    first = start or (simulated[0]["t"] if simulated else "")
    last = end or (simulated[-1]["t"] if simulated else "")
    observed = usgs_observed(gage, first, last) if first and last else []
    teehr = teehr_metrics(root)
    scores = teehr or skill_scores(observed, simulated, start)
    note = ""
    if simulated:
        note = f"Simulated series is the NextGen nexus {nexus} CSV (m³/s). USGS observations are converted from ft³/s."
        if (root / "ngen-run" / "outputs" / "troute").is_dir():
            note += " t-route also wrote parquet files; those are the routed hydrograph TEEHR uses."
    elif observed:
        note = "USGS observations are available. Simulated streamflow is not in CSV yet, so the chart shows observations only."
    elif (root / "ngen-run" / "teehr").is_dir() and not teehr:
        note = "TEEHR wrote an evaluation folder, but no metrics.csv was found. Open ngen-run/teehr for the warehouse files."
    return {
        "nexus": nexus,
        "observed": observed,
        "simulated": simulated,
        "scores": scores,
        "note": note,
    }
