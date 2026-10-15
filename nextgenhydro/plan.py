def build_plan(location: str, request: dict, realization: str, output_dir: str, realization_specified: bool) -> dict:
    return {
        "location": location,
        "gage": request.get("gage", ""),
        "start": request.get("start", ""),
        "end": request.get("end", ""),
        "forcing": request.get("forcing", ""),
        "realization": realization if realization_specified else "",
        "outputDir": output_dir.strip(),
    }
