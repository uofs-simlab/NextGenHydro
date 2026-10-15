def watershed_geopackage(gage: str) -> str:
    return f"~/ngiab_preprocess_output/gage-{gage}/config/gage-{gage}_subset.gpkg"


def resolve_watershed_geopackage(gage: str, home: str) -> str:
    return f"{home}/ngiab_preprocess_output/gage-{gage}/config/gage-{gage}_subset.gpkg"
