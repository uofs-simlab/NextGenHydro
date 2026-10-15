import json
import re
import urllib.request


def display_station_name(raw: str) -> str:
    titled = re.sub(r"\b[a-z]", lambda match: match.group(0).upper(), raw.lower())
    return re.sub(r", ([A-Za-z]{2})$", lambda match: f", {match.group(1).upper()}", titled)


def _rdb_record(text: str) -> dict | None:
    rows = [line.strip() for line in re.split(r"\r?\n", text) if line.strip() and not line.startswith("#")]
    if len(rows) < 3:
        return None
    return {"headers": rows[0].split("\t"), "values": rows[2].split("\t")}


def _rdb_field(record: dict, name: str) -> str:
    try:
        index = record["headers"].index(name)
    except ValueError:
        return ""
    if index >= len(record["values"]):
        return ""
    return record["values"][index].strip()


def station_name_from_rdb(text: str) -> str | None:
    record = _rdb_record(text)
    if not record:
        return None
    name = _rdb_field(record, "station_nm")
    return display_station_name(name) if name else None


def station_point_from_rdb(text: str) -> dict | None:
    record = _rdb_record(text)
    if not record:
        return None
    lat_text = _rdb_field(record, "dec_lat_va")
    lng_text = _rdb_field(record, "dec_long_va")
    if not lat_text or not lng_text:
        return None
    try:
        lat = float(lat_text)
        lng = float(lng_text)
    except ValueError:
        return None
    if abs(lat) > 90 or abs(lng) > 180:
        return None
    return {"lat": lat, "lng": lng}


def _fetch(url: str, timeout: float = 8) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return response.read().decode("utf-8", "replace")
    except Exception:
        return None


def lookup_station_name(gage: str) -> str | None:
    text = _fetch(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&sites={gage}&siteStatus=all")
    if text is None:
        return None
    return station_name_from_rdb(text)


def lookup_station_point(gage: str) -> dict | None:
    text = _fetch(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&sites={gage}&siteStatus=all")
    if text is None:
        return None
    return station_point_from_rdb(text)


def parse_site_rows(text: str) -> list[dict]:
    from .agent import is_gage_id

    rows = [line.strip() for line in re.split(r"\r?\n", text) if line.strip() and not line.startswith("#")]
    if len(rows) < 3:
        return []
    headers = rows[0].split("\t")
    try:
        id_at = headers.index("site_no")
        lat_at = headers.index("dec_lat_va")
        lng_at = headers.index("dec_long_va")
    except ValueError:
        return []
    name_at = headers.index("station_nm") if "station_nm" in headers else -1
    type_at = headers.index("site_tp_cd") if "site_tp_cd" in headers else -1
    sites: list[dict] = []
    seen: set[str] = set()
    for line in rows[2:]:
        cells = line.split("\t")
        site_id = cells[id_at].strip() if id_at < len(cells) else ""
        lat_text = cells[lat_at].strip() if lat_at < len(cells) else ""
        lng_text = cells[lng_at].strip() if lng_at < len(cells) else ""
        kind = "ST" if type_at < 0 else (cells[type_at].strip() if type_at < len(cells) else "")
        if not is_gage_id(site_id) or site_id in seen or kind != "ST" or not lat_text or not lng_text:
            continue
        try:
            lat = float(lat_text)
            lng = float(lng_text)
        except ValueError:
            continue
        if abs(lat) > 90 or abs(lng) > 180:
            continue
        raw_name = cells[name_at].strip() if name_at >= 0 and name_at < len(cells) else ""
        seen.add(site_id)
        sites.append({"id": site_id, "name": display_station_name(raw_name) if raw_name else f"USGS {site_id}", "lat": lat, "lng": lng})
    return sites


def search_places(query: str) -> list[dict]:
    url = "https://photon.komoot.io/api/?q=" + urllib.request.quote(query) + "&limit=6&lat=39.8&lon=-98.6"
    text = _fetch(url, timeout=12)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    hits = []
    for feature in payload.get("features") or []:
        coordinates = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        props = feature.get("properties") or {}
        if coordinates[0] is None or coordinates[1] is None:
            continue
        detail = ", ".join(part for part in [props.get("city"), props.get("state"), props.get("country")] if part)
        kind = props.get("osm_value")
        zoom = 9 if kind in {"river", "stream"} else 6 if kind == "state" else 11
        label = props.get("name") or detail or "Place"
        if label == "Place" and not detail:
            continue
        hits.append({"label": label, "detail": detail, "lng": coordinates[0], "lat": coordinates[1], "zoom": zoom})
    return hits
