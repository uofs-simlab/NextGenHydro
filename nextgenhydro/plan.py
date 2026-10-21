def _nprocs(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 4
    if number < 1:
        return 4
    return min(number, 256)


def plan_coordinates(sentence: str, gage: str) -> dict:
    from pathlib import Path

    from .agent import is_gage_id, read_named_coordinates
    from .site_name import lookup_station_point
    from .watershed import resolve_watershed_geopackage
    from .watershed_geojson import hydrofabric_outlet

    named = read_named_coordinates(sentence)
    user_point = named if named and named.get("valid") else None
    station = lookup_station_point(gage) if is_gage_id(gage) else None
    fabric = hydrofabric_outlet(resolve_watershed_geopackage(gage, str(Path.home())), gage) if is_gage_id(gage) else None
    gauge_latitude = None if not station else station["lat"]
    gauge_longitude = None if not station else station["lng"]
    if user_point:
        outlet_latitude, outlet_longitude = user_point["lat"], user_point["lng"]
    elif fabric:
        outlet_latitude, outlet_longitude = fabric["latitude"], fabric["longitude"]
    else:
        outlet_latitude, outlet_longitude = gauge_latitude, gauge_longitude
    return {
        "gauge_latitude": gauge_latitude,
        "gauge_longitude": gauge_longitude,
        "outlet_latitude": outlet_latitude,
        "outlet_longitude": outlet_longitude,
    }


def build_plan(location: str, request: dict, realization: str, output_dir: str, realization_specified: bool, action: str, logging: str, nprocs: int, note: str, latitude: float | None = None, longitude: float | None = None, outlet_latitude: float | None = None, outlet_longitude: float | None = None) -> dict:
    if outlet_latitude is None and outlet_longitude is None:
        outlet_latitude, outlet_longitude = latitude, longitude
    return {
        "location": location,
        "gauge": {
            "gauge number": request.get("gage", ""),
            "gauge latitude": latitude,
            "gauge longitude": longitude,
        },
        "outlet": {
            "outlet latitude": outlet_latitude,
            "outlet longitude": outlet_longitude,
        },
        "start": request.get("start", ""),
        "end": request.get("end", ""),
        "forcing": request.get("forcing", ""),
        "realization": realization if realization_specified else "",
        "outputDir": output_dir.strip(),
        "action": action if action in {"run", "dry run", "do not run"} else "",
        "logging": "verbose" if logging == "verbose" else "",
        "nprocs": _nprocs(nprocs),
        "note": note.strip(),
    }
