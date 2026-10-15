import struct

from .albers5070 import albers5070_to_lon_lat


def _envelope_bytes(flags: int) -> int:
    kind = (flags >> 1) & 0x07
    if kind == 1:
        return 32
    if kind in {2, 3}:
        return 48
    if kind == 4:
        return 64
    return 0


def _read_wkb(blob: bytes, offset: int) -> tuple[dict, int]:
    endian = blob[offset] == 1
    order = "<" if endian else ">"
    geo_type = struct.unpack_from(order + "I", blob, offset + 1)[0]
    cursor = offset + 5
    has_z = (geo_type & 0x80000000) != 0
    has_m = (geo_type & 0x40000000) != 0
    has_srid = (geo_type & 0x20000000) != 0
    dims = 2 + (1 if has_z else 0) + (1 if has_m else 0)
    if has_srid:
        cursor += 4
    base = geo_type & 0xFF

    def read_position() -> list[float]:
        nonlocal cursor
        x, y = struct.unpack_from(order + "dd", blob, cursor)
        cursor += dims * 8
        return albers5070_to_lon_lat(x, y)

    def read_positions(count: int) -> list[list[float]]:
        return [read_position() for _ in range(count)]

    def read_count() -> int:
        nonlocal cursor
        count = struct.unpack_from(order + "I", blob, cursor)[0]
        cursor += 4
        return count

    if base == 1:
        return {"type": "Point", "coordinates": read_position()}, cursor
    if base == 2:
        return {"type": "LineString", "coordinates": read_positions(read_count())}, cursor
    if base == 3:
        rings = [read_positions(read_count()) for _ in range(read_count())]
        return {"type": "Polygon", "coordinates": rings}, cursor
    if base == 5:
        lines = []
        for _ in range(read_count()):
            part, cursor = _read_wkb(blob, cursor)
            if part["type"] != "LineString":
                raise ValueError("A flowpath part is not a line.")
            lines.append(part["coordinates"])
        return {"type": "MultiLineString", "coordinates": lines}, cursor
    if base == 6:
        polygons = []
        for _ in range(read_count()):
            part, cursor = _read_wkb(blob, cursor)
            if part["type"] != "Polygon":
                raise ValueError("A catchment part is not a polygon.")
            polygons.append(part["coordinates"])
        return {"type": "MultiPolygon", "coordinates": polygons}, cursor
    raise ValueError(f"Unsupported geometry type {base}.")


def geometry_from_geopackage(blob: bytes) -> dict | None:
    if len(blob) < 8 or blob[0] != 0x47 or blob[1] != 0x50:
        return None
    start = 8 + _envelope_bytes(blob[3])
    if start >= len(blob):
        return None
    geometry, _offset = _read_wkb(blob, start)
    return geometry
