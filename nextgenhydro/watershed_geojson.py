import math
import os
import re
import sqlite3
import time

from .gpkg_geometry import geometry_from_geopackage

_CACHE: dict[str, dict] = {}


def _visit(geometry: dict, bounds: list[float]) -> None:
    def walk(positions: list) -> None:
        for lon, lat in positions:
            bounds[0] = lon if bounds[0] is None or lon < bounds[0] else bounds[0]
            bounds[1] = lat if bounds[1] is None or lat < bounds[1] else bounds[1]
            bounds[2] = lon if bounds[2] is None or lon > bounds[2] else bounds[2]
            bounds[3] = lat if bounds[3] is None or lat > bounds[3] else bounds[3]

    kind = geometry["type"]
    if kind == "Point":
        walk([geometry["coordinates"]])
    elif kind == "LineString":
        walk(geometry["coordinates"])
    elif kind in {"Polygon", "MultiLineString"}:
        for ring in geometry["coordinates"]:
            walk(ring)
    else:
        for polygon in geometry["coordinates"]:
            for ring in polygon:
                walk(ring)


def watershed_geojson(gpkg: str) -> dict:
    stamp = os.stat(gpkg).st_mtime
    hit = _CACHE.get(gpkg)
    if hit and hit["stamp"] == stamp:
        return hit["body"]
    connection = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        bounds: list[float | None] = [None, None, None, None]
        divides = []
        for divide_id, geom in connection.execute("SELECT divide_id, geom FROM divides"):
            if not isinstance(geom, (bytes, bytearray)):
                continue
            geometry = geometry_from_geopackage(geom)
            if not geometry:
                continue
            _visit(geometry, bounds)
            divides.append({"type": "Feature", "properties": {"divide_id": str(divide_id or "")}, "geometry": geometry})
        flowlines = []
        for feature_id, stream_order, geom in connection.execute('SELECT id, "order" AS stream_order, geom FROM flowpaths'):
            if not isinstance(geom, (bytes, bytearray)):
                continue
            geometry = geometry_from_geopackage(geom)
            if not geometry:
                continue
            _visit(geometry, bounds)
            try:
                order = int(round(float(stream_order)))
            except (TypeError, ValueError):
                order = 1
            flowlines.append({"type": "Feature", "properties": {"id": str(feature_id or ""), "stream_order": order}, "geometry": geometry})
        match = re.search(r"gage-(\d+)_subset\.gpkg$", gpkg)
        gage_id = match.group(1) if match else ""
        gage = []
        for x, y in connection.execute("SELECT hl_x, hl_y FROM hydrolocations WHERE hl_link = ?", (gage_id,)):
            try:
                coordinates = __import__("nextgenhydro.albers5070", fromlist=["albers5070_to_lon_lat"]).albers5070_to_lon_lat(float(x), float(y))
            except (TypeError, ValueError):
                continue
            geometry = {"type": "Point", "coordinates": coordinates}
            _visit(geometry, bounds)
            gage.append({"type": "Feature", "properties": {"id": gage_id}, "geometry": geometry})
        box = [[bounds[0] if bounds[0] is not None else math.nan, bounds[1] if bounds[1] is not None else math.nan], [bounds[2] if bounds[2] is not None else math.nan, bounds[3] if bounds[3] is not None else math.nan]]
        flat = [box[0][0], box[0][1], box[1][0], box[1][1]]
        if not divides or any(not math.isfinite(value) for value in flat):
            age_ms = (time.time() - stamp) * 1000
            if age_ms > 3000:
                raise RuntimeError("The watershed file has no catchments.")
            raise RuntimeError("WATERSHED_WRITING")
        body = {
            "divides": {"type": "FeatureCollection", "features": divides},
            "flowlines": {"type": "FeatureCollection", "features": flowlines},
            "gage": {"type": "FeatureCollection", "features": gage},
            "bounds": box,
        }
        _CACHE[gpkg] = {"stamp": stamp, "body": body}
        return body
    finally:
        connection.close()
