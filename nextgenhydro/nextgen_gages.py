import os
import sqlite3
import threading

from .agent import is_gage_id

HYDROFABRIC = os.path.expanduser("~/.ngiab/hydrofabric/v2.2/conus_nextgen.gpkg")
_DATABASE: sqlite3.Connection | None | bool = False
_LOCK = threading.Lock()


def _open() -> sqlite3.Connection | None:
    global _DATABASE
    if _DATABASE is not False:
        return _DATABASE if isinstance(_DATABASE, sqlite3.Connection) else None
    if not os.path.exists(HYDROFABRIC):
        _DATABASE = None
        return None
    try:
        _DATABASE = sqlite3.connect(f"file:{HYDROFABRIC}?mode=ro", uri=True, check_same_thread=False)
    except sqlite3.Error:
        _DATABASE = None
    return _DATABASE if isinstance(_DATABASE, sqlite3.Connection) else None


def gage_in_hydrofabric(gage: str) -> bool | None:
    with _LOCK:
        database = _open()
        if database is None:
            return None
        if not is_gage_id(gage):
            return False
        row = database.execute('SELECT 1 FROM "flowpath-attributes" WHERE gage = ? LIMIT 1', (gage,)).fetchone()
        return row is not None


def nextgen_gage_ids(ids: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for gage in ids:
        text = str(gage).strip()
        if text in seen or not is_gage_id(text):
            continue
        seen.add(text)
        unique.append(text)
    if not unique:
        return []
    with _LOCK:
        database = _open()
        if database is None:
            return []
        marks = ",".join("?" for _ in unique)
        found = {str(row[0]) for row in database.execute(f'SELECT gage FROM "flowpath-attributes" WHERE gage IN ({marks})', unique) if row[0]}
    return [gage for gage in unique if gage in found]
