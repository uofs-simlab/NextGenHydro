import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nextgenhydro.agent import fallback_answer, location_after_gage_pick, named_location
from nextgenhydro.datastream_command import datastream_command
from nextgenhydro.nearest_gages import keep_near_stations
from nextgenhydro.nlp import agent_system_prompt, interpret_forcing, interpret_realization
from nextgenhydro.parse_request import parse_request
from nextgenhydro.place_query import place_query_from_sentence

denver = "Simulate a watershed near Denver using the latest available historical data."
assert place_query_from_sentence(denver) == "Denver"
assert fallback_answer(denver)["patch"]["location"] == "Denver"
assert fallback_answer(denver)["patch"]["gage"] == ""
assert fallback_answer("Run a hydrological simulation for a watershed in Colorado.")["patch"]["location"] == "Colorado"
assert named_location("Run USGS gage 01491000 from March 2020.", "Choptank River Near Greensboro, MD") == "Choptank River Near Greensboro, MD"
assert location_after_gage_pick("Colorado", "Choptank River Near Greensboro, MD") == "Colorado"

identify = "Identify the watershed upstream of USGS gage 01646500 and prepare its HydroFabric subset."
assert interpret_realization(identify)["realization"] == ""
held = "Prepare meteorological forcing for USGS gauge 01646500 for the first week of January 2021, but do not run the simulation."
assert interpret_realization(held)["realization"] == ""
held_dates = parse_request(held)
assert held_dates["gage"] == "01646500"
assert held_dates["start"] == "2021-01-01T00:00"
assert held_dates["end"] == "2021-01-07T00:00"
assert interpret_forcing(held, held_dates)["forcing"] == "NWM_RETRO_V3"
assert interpret_forcing(identify)["forcing"] == ""
parsed = parse_request(identify)
assert parsed["gage"] == "01646500"
assert parsed["start"] == ""

potomac = "Run a NextGen simulation for the watershed draining to USGS gage 01646500 from January 1, 2020, to January 10, 2020."
assert interpret_realization(potomac)["realization"] == "realization_sloth_nom_cfe_pet_troute.json"
assert interpret_forcing(potomac, parse_request(potomac))["forcing"] == "NWM_RETRO_V3"
assert "near Denver has location Denver" in agent_system_prompt()
assert "asks to run or simulate" in agent_system_prompt()
assert "first week of July 2020" in agent_system_prompt()
for sentence in (
    "July 1–7, 2020",
    "2020/July/01 , 2020/July/07",
    "2020-July-01 - 2020-July-07",
    "through first week of July 2020",
    "2020-07-01 , 2020-07-07",
    "2020/07/01 - 2020/07/07",
    "2020\\07\\01 - 2020\\07\\07",
):
    parsed_july = parse_request(sentence)
    assert parsed_july["start"] == "2020-07-01T00:00", sentence
    assert parsed_july["end"] == "2020-07-07T00:00", sentence

command = datastream_command(
    {"gage": "09106150", "start": "2020-05-10T00:00", "end": "2020-06-21T00:00", "forcing": "NWM_RETRO_V3"},
    {"outputDir": "./data/palisade", "realization": "realization_sloth_nom_cfe_pet_troute.json"},
)
assert command["argv"][:6] == ["-s", "202005100000", "-e", "202006210000", "-C", "NWM_RETRO_V3"]

near = keep_near_stations(
    [
        {"id": "a", "miles": 1, "lat": 39, "lng": -106},
        {"id": "b", "miles": 2, "lat": 39.01, "lng": -106.01},
        {"id": "c", "miles": 3, "lat": 39.02, "lng": -106.02},
        {"id": "d", "miles": 400, "lat": 30, "lng": -90},
    ]
)
assert [item["id"] for item in near] == ["a", "b", "c"]
print("python checks ok")
