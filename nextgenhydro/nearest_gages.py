import math
import urllib.parse
import urllib.request

from .site_name import parse_site_rows

SPANS = [2, 4, 6]
SOUTH_SHIFTS = [0, 5, 10]


def miles_between(a: dict, b: dict) -> float:
    radius = 3958.8
    to_rad = math.pi / 180
    d_lat = (b["lat"] - a["lat"]) * to_rad
    d_lng = (b["lng"] - a["lng"]) * to_rad
    step = math.sin(d_lat / 2) ** 2 + math.cos(a["lat"] * to_rad) * math.cos(b["lat"] * to_rad) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(min(1, math.sqrt(step)))


def closest_gages(origin: dict, sites: list[dict], limit: int = 5) -> list[dict]:
    ranked = [{**site, "miles": miles_between(origin, site)} for site in sites]
    ranked.sort(key=lambda item: (item["miles"], item["id"]))
    return ranked[:limit]


def keep_near_stations(gages: list[dict], limit: int = 5) -> list[dict]:
    sorted_gages = sorted(gages, key=lambda item: (item["miles"], item["id"]))
    if len(sorted_gages) <= 2:
        return sorted_gages[:limit]
    first, second = sorted_gages[0], sorted_gages[1]
    far = max(30, miles_between(first, second) * 3)
    kept = [first, second]
    for gage in sorted_gages[2:limit]:
        if min(miles_between(gage, first), miles_between(gage, second)) > far:
            break
        kept.append(gage)
    return kept


def _box(origin: dict, span: float) -> tuple[float, float, float, float]:
    half = span / 2
    return (
        max(-180, origin["lng"] - half),
        max(-90, origin["lat"] - half),
        min(180, origin["lng"] + half),
        min(90, origin["lat"] + half),
    )


def bounds_for_gages(gages: list[dict]) -> list[list[float]] | None:
    points = [gage for gage in gages if gage.get("lng") is not None and gage.get("lat") is not None]
    if not points:
        return None
    west = min(gage["lng"] for gage in points)
    east = max(gage["lng"] for gage in points)
    south = min(gage["lat"] for gage in points)
    north = max(gage["lat"] for gage in points)
    pad = 0.2
    if east - west < pad:
        mid = (east + west) / 2
        west, east = mid - pad / 2, mid + pad / 2
    if north - south < pad:
        mid = (north + south) / 2
        south, north = mid - pad / 2, mid + pad / 2
    return [[west, south], [east, north]]


def lookup_nearest_gages(origin: dict, allowed) -> list[dict]:
    pooled: list[dict] = []
    seen: set[str] = set()
    for shift in SOUTH_SHIFTS:
        center = {"lat": origin["lat"] - shift, "lng": origin["lng"]}
        for span in SPANS:
            west, south, east, north = _box(center, span)
            query = urllib.parse.urlencode(
                {
                    "format": "rdb",
                    "bBox": f"{west},{south},{east},{north}",
                    "siteType": "ST",
                    "siteStatus": "all",
                    "parameterCd": "00060",
                }
            )
            try:
                with urllib.request.urlopen(f"https://waterservices.usgs.gov/nwis/site/?{query}", timeout=20) as response:
                    text = response.read().decode("utf-8", "replace")
            except Exception:
                continue
            for site in parse_site_rows(text):
                if site["id"] in seen:
                    continue
                seen.add(site["id"])
                pooled.append(site)
            if len(pooled) >= 120:
                break
        if len(pooled) >= 120:
            break
    ranked = closest_gages(origin, pooled, 80)
    present = set(allowed([gage["id"] for gage in ranked]))
    return keep_near_stations([gage for gage in ranked if gage["id"] in present])
