import os
import re
import sqlite3

SCIENTIFIC_ID = re.compile(r"^([A-Za-z]+-)(\d+)e\+(\d+)$", re.I)


def plain_hydro_id(value: str) -> str | None:
    match = SCIENTIFIC_ID.fullmatch(value)
    if not match:
        return None
    coefficient = int(match.group(2))
    exponent = int(match.group(3))
    return f"{match.group(1)}{coefficient * 10 ** exponent}"


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def repair_watershed_ids(gpkg: str) -> list[dict]:
    connection = sqlite3.connect(gpkg)
    repairs: list[dict] = []
    triggers = connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND sql IS NOT NULL").fetchall()
    try:
        connection.execute("BEGIN")
        for name, _sql in triggers:
            connection.execute(f"DROP TRIGGER IF EXISTS {_quote(name)}")
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        for (table,) in tables:
            if re.match(r"^(?:rtree_|gpkg_|sqlite_)", table):
                continue
            columns = connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
            for column in columns:
                kind = (column[2] or "").upper()
                if kind not in {"TEXT", "VARCHAR", ""}:
                    continue
                quoted_table = _quote(table)
                quoted_column = _quote(column[1])
                try:
                    values = connection.execute(
                        f"SELECT DISTINCT {quoted_column} AS value FROM {quoted_table} WHERE {quoted_column} LIKE '%e+%'"
                    ).fetchall()
                except sqlite3.Error:
                    continue
                for (value,) in values:
                    if not isinstance(value, str):
                        continue
                    nxt = plain_hydro_id(value)
                    if not nxt or nxt == value:
                        continue
                    cursor = connection.execute(
                        f"UPDATE {quoted_table} SET {quoted_column} = ? WHERE {quoted_column} = ?",
                        (nxt, value),
                    )
                    repairs.append({"from": value, "to": nxt, "count": cursor.rowcount})
        for _name, sql in triggers:
            connection.executescript(sql)
        connection.execute("COMMIT")
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()
    return repairs
