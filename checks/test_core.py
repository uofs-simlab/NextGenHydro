import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nextgenhydro.agent import drop_unknown_gage, fallback_answer, finish_ask, flag_inverted_dates, location_after_gage_pick, named_location, read_named_coordinates, restore_known_gage, sanitize_agent_patch, with_valid_gage_point
from nextgenhydro.plan import build_plan, plan_coordinates
from nextgenhydro.nextgen_gages import gage_in_hydrofabric
from nextgenhydro.datastream_command import datastream_command
from nextgenhydro.nearest_gages import bounds_for_gages, keep_near_stations
from nextgenhydro.site_name import choose_place_hit
from nextgenhydro.nlp import agent_system_prompt, interpret_action, interpret_forcing, interpret_logging, interpret_nprocs, interpret_realization
from nextgenhydro.review import note_from_feedback, review_plan
from nextgenhydro.realizations import DEFAULT_REALIZATION
from nextgenhydro.repair_watershed_ids import repair_watershed_ids
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
assert interpret_action(held) == "do not run"
assert interpret_action(identify) == ""
prepare = "Prepare the HydroFabric and forcing data for USGS gauge 03339000, then stop before model execution."
prepare_dates = parse_request(prepare)
assert prepare_dates["gage"] == "03339000"
assert prepare_dates["start"] == ""
assert prepare_dates["end"] == ""
assert interpret_action(prepare) == "do not run"
assert interpret_realization(prepare)["realization"] == ""
assert interpret_forcing(prepare, prepare_dates)["forcing"] == "NWM_RETRO_V3"
assert fallback_answer(prepare)["patch"]["outputDir"] == ""
assert fallback_answer(prepare)["patch"]["logging"] == ""
realization_only = "Generate the realization configuration and BMI model inputs for USGS gauge 09106150 without executing NextGen."
assert interpret_realization(realization_only)["realization"] == DEFAULT_REALIZATION
assert interpret_action(realization_only) == "do not run"
assert fallback_answer(realization_only)["patch"]["gage"] == "09106150"
assert fallback_answer(realization_only)["patch"]["action"] == "do not run"
workflow = "Generate a complete workflow plan for a NextGen simulation above USGS gauge 09106150, but do not execute any steps."
workflow_dates = parse_request(workflow)
assert workflow_dates["gage"] == "09106150"
assert workflow_dates["start"] == ""
assert workflow_dates["end"] == ""
assert interpret_realization(workflow)["realization"] == DEFAULT_REALIZATION
assert interpret_forcing(workflow, workflow_dates)["forcing"] == "NWM_RETRO_V3"
assert interpret_action(workflow) == "do not run"
assert fallback_answer(workflow)["patch"]["outputDir"] == ""
dry = "Perform a dry run of the NextGen workflow for USGS gauge 01646500 from June 1–3, 2020."
dry_dates = parse_request(dry)
assert dry_dates["gage"] == "01646500"
assert dry_dates["start"] == "2020-06-01T00:00"
assert dry_dates["end"] == "2020-06-03T00:00"
assert interpret_action(dry) == "dry run"
assert interpret_realization(dry)["realization"] == DEFAULT_REALIZATION
assert interpret_forcing(dry, dry_dates)["forcing"] == "NWM_RETRO_V3"
assert fallback_answer(dry)["patch"]["action"] == "dry run"
dry_command = datastream_command(
    {"gage": "01646500", "start": "2020-06-01T00:00", "end": "2020-06-03T00:00", "forcing": "NWM_RETRO_V3"},
    {"outputDir": "./data/potomac-dry", "realization": DEFAULT_REALIZATION, "action": "dry run"},
)
assert dry_command["argv"][-2:] == ["-y", "True"]

import sqlite3
import tempfile

repair_path = tempfile.mktemp(suffix=".gpkg")
repair_db = sqlite3.connect(repair_path)
repair_db.execute("CREATE TABLE divides (divide_id TEXT)")
repair_db.execute("INSERT INTO divides VALUES ('cat-1e+6')")
repair_db.execute("CREATE TRIGGER keep_divide AFTER UPDATE ON divides BEGIN SELECT 1; END")
repair_db.commit()
repair_db.close()
assert repair_watershed_ids(repair_path)[0]["to"] == "cat-1000000"
assert interpret_forcing(identify)["forcing"] == ""
parsed = parse_request(identify)
assert parsed["gage"] == "01646500"
assert parsed["start"] == ""
missed_slash = parse_request("simulate the routes form gauge 01012500 from 2002/0402 to 2002/05/10")
assert missed_slash["gage"] == "01012500"
assert missed_slash["start"] == "2002-04-02T00:00"
assert missed_slash["end"] == "2002-05-10T00:00"
kept_by_model = sanitize_agent_patch({
    "gage": "01012500",
    "start": "2002-04-02T00:00",
    "end": "2002-05-10T00:00",
    "forcing": "NWM_RETRO_V3",
    "realization": "realization_sloth_nom_cfe_pet_troute.json",
    "action": "run",
    "logging": "",
    "nprocs": 4,
    "note": "Read 2002/0402 as April 2.",
})
assert kept_by_model["start"] == "2002-04-02T00:00"
assert kept_by_model["end"] == "2002-05-10T00:00"
assert kept_by_model["action"] == "run"
impossible = "Run a simulation for a watershed at latitude 120 and longitude -200."
impossible_point = read_named_coordinates(impossible)
assert impossible_point["valid"] is False
impossible_patch = finish_ask(
    {
        "patch": {
            "gage": "",
            "start": "",
            "end": "",
            "forcing": "",
            "realization": "realization_sloth_nom_cfe_pet_troute.json",
            "lat": None,
            "lng": None,
            "outputDir": "",
            "location": "a watershed at latitude 120 and longitude -200",
            "action": "run",
            "logging": "",
            "nprocs": 4,
            "note": "Location is a watershed at latitude 120 and longitude -200.",
        },
        "note": "",
        "usedModel": True,
    },
    impossible,
)["patch"]
assert impossible_patch["location"] == ""
assert impossible_patch["lat"] is None
assert impossible_patch["lng"] is None
assert impossible_patch["action"] == "do not run"
assert "outside -90 to 90" in impossible_patch["note"]
assert "outside -180 to 180" in impossible_patch["note"]
quoted = read_named_coordinates('upstream of "outlet latitude": 38, "outlet longitude": -77 from June 1')
assert quoted == {"lat": 38.0, "lng": -77.0, "valid": True}
possible = read_named_coordinates("Run a simulation at latitude 39.11 and longitude -108.35.")
assert possible["valid"] is True
assert possible["lat"] == 39.11
assert possible["lng"] == -108.35

potomac = "Run a NextGen simulation for the watershed draining to USGS gage 01646500 from January 1, 2020, to January 10, 2020."
assert interpret_realization(potomac)["realization"] == "realization_sloth_nom_cfe_pet_troute.json"
assert interpret_action(potomac) == "run"
assert interpret_logging(potomac) == ""
verbose = "Run a NextGen simulation for USGS gauge 09106150 with verbose logging enabled."
assert interpret_logging(verbose) == "verbose"
assert interpret_action(verbose) == "run"
assert fallback_answer(verbose)["patch"]["logging"] == "verbose"
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
assert command["argv"][command["argv"].index("-g") + 1] == "~/ngiab_preprocess_output/gage-09106150/config/gage-09106150_subset.gpkg"
assert "-V" not in command["argv"]
assert command["argv"][command["argv"].index("-n") + 1] == "4"
assert gage_in_hydrofabric("01646500") is True
assert gage_in_hydrofabric("99999999") is False
fake = "Run NextGen for USGS gage 99999999 from June 1–5, 2020."
rejected = finish_ask(fallback_answer(fake), fake)["patch"]
assert rejected["gage"] == ""
assert rejected["location"] == ""
assert rejected["action"] == "do not run"
assert rejected["lat"] is None
assert rejected["lng"] is None
assert "not a NextGen gauge" in rejected["note"]
cleared = with_valid_gage_point({"gage": "99999999", "lat": 1.0, "lng": 2.0})
assert cleared["lat"] is None and cleared["lng"] is None
assert drop_unknown_gage({"gage": "01646500", "location": "", "note": ""}, "Run USGS gage 01646500.")["gage"] == "01646500"
kept = drop_unknown_gage(
    {
        "gage": "09106150",
        "location": "Colo River Below Grand Valley Div Nr Palisade, CO",
        "note": "Gage 09106150 left blank as not a NextGen station and start is after end so action set to do not run.",
    },
    "Simulate USGS gauge 09106150 from December 31, 2021, to January 1, 2020.",
)
assert kept["gage"] == "09106150"
assert "left blank" not in kept["note"].lower()
assert "not a NextGen" not in kept["note"]
assert "start is after end" in kept["note"]
backwards = "Simulate USGS gauge 09106150 from December 31, 2021, to January 1, 2020."
backwards_patch = finish_ask(fallback_answer(backwards), backwards)["patch"]
assert backwards_patch["gage"] == "09106150"
assert backwards_patch["start"] == "2021-12-31T00:00"
assert backwards_patch["end"] == "2020-01-01T00:00"
assert backwards_patch["action"] == "do not run"
assert "not before" in backwards_patch["note"]
assert flag_inverted_dates({"start": "2020-01-01T00:00", "end": "2021-12-31T00:00", "action": "run", "note": ""})["action"] == "run"
planned = build_plan("", {"gage": "", "start": "", "end": "", "forcing": ""}, "", "", False, "run", "", 4, "USGS 99999999 is not a NextGen gage.")
assert planned["note"] == "USGS 99999999 is not a NextGen gage."
assert planned["gauge"]["gauge number"] == ""
assert planned["gauge"]["gauge latitude"] is None
assert planned["gauge"]["gauge longitude"] is None
placed = build_plan("", {"gage": "01646500", "start": "", "end": "", "forcing": ""}, "", "", False, "run", "", 4, "", 38.9496, -77.1279)
assert placed["gauge"]["gauge number"] == "01646500"
assert placed["gauge"]["gauge latitude"] == 38.9496
assert placed["gauge"]["gauge longitude"] == -77.1279
assert placed["outlet"]["outlet latitude"] == 38.9496
assert placed["outlet"]["outlet longitude"] == -77.1279
potomac_points = plan_coordinates("Run USGS gauge 01646500.", "01646500")
assert abs(potomac_points["gauge_latitude"] - 38.94977778) < 1e-4
assert abs(potomac_points["outlet_latitude"] - 38.94139) < 1e-3
assert abs(potomac_points["gauge_latitude"] - potomac_points["outlet_latitude"]) > 1e-3
asked_outlet = plan_coordinates("Run a simulation at latitude 39.11 and longitude -108.35.", "09106150")
assert asked_outlet["outlet_latitude"] == 39.11
assert asked_outlet["outlet_longitude"] == -108.35
assert abs(asked_outlet["gauge_latitude"] - 39.09859226) < 1e-3
assert interpret_nprocs("Run a NextGen simulation.") == 4
assert interpret_nprocs("Run a NextGen simulation with 8 processes.") == 8
assert fallback_answer("Run a NextGen simulation with 8 processes.")["patch"]["nprocs"] == 8
verbose_command = datastream_command(
    {"gage": "09106150", "start": "2020-05-10T00:00", "end": "2020-06-21T00:00", "forcing": "NWM_RETRO_V3"},
    {"outputDir": "./data/palisade", "realization": "realization_sloth_nom_cfe_pet_troute.json", "logging": "verbose"},
)
assert verbose_command["argv"][-2:] == ["-V", "True"]

near = keep_near_stations(
    [
        {"id": "a", "miles": 1, "lat": 39, "lng": -106},
        {"id": "b", "miles": 2, "lat": 39.01, "lng": -106.01},
        {"id": "c", "miles": 3, "lat": 39.02, "lng": -106.02},
        {"id": "d", "miles": 400, "lat": 30, "lng": -90},
    ]
)
assert [item["id"] for item in near] == ["a", "b", "c"]
ottawa = {"label": "Upper Carp River Detention Basin", "detail": "Ottawa, Ontario, Canada", "lat": 45.28, "lng": -75.89, "zoom": 11}
colorado = {"label": "Upper Basin", "detail": "Allenspark, Colorado, United States", "lat": 40.14, "lng": -105.52, "zoom": 11}
assert choose_place_hit("Upper Colorado River Basin", [ottawa, colorado])["detail"].endswith("United States")
station_box = bounds_for_gages(
    [
        {"lat": 39.1, "lng": -108.3},
        {"lat": 39.5, "lng": -107.8},
    ]
)
assert station_box[0][0] <= -108.3 and station_box[1][0] >= -107.8
assert station_box[0][1] <= 39.1 and station_box[1][1] >= 39.5
no_download = "Run NextGen for USGS gauge 01646500 without downloading forcing data or using existing forcing files."
restored = restore_known_gage(
    {
        "gage": "",
        "start": "",
        "end": "",
        "forcing": "",
        "realization": "",
        "action": "do not run",
        "note": "01646500 is not a NextGen gauge, so not running.",
    },
    no_download,
)
assert restored["gage"] == "01646500"
assert restored["action"] == "run"
assert restored["forcing"] == ""
assert restored["realization"] == "realization_sloth_nom_cfe_pet_troute.json"
assert "not a NextGen" not in restored["note"]
assert "No model was named" in restored["note"]
assert "copy those digits into gage" in agent_system_prompt()
assert "check_gauge" in agent_system_prompt()
assert "check_models" in agent_system_prompt()
assert "messages those functions return" in agent_system_prompt()
unsupported_models = "Run a NextGen simulation for USGS gauge 09106150 using Snow17, SAC-SMA, and UHG, and report which components are actually supported."
unsupported_choice = interpret_realization(unsupported_models, ["UHG"])
assert unsupported_choice["realization"] == ""
assert unsupported_choice["source"] == "unsupported"
assert "Snow17" in unsupported_choice["note"] and "Sac-SMA" in unsupported_choice["note"] and "UHG" in unsupported_choice["note"]
assert "not supported in this repo for now" in unsupported_choice["note"]
assert "No model was named" not in unsupported_choice["note"]
rejected_models = review_plan(
    unsupported_models,
    {
        "gage": "09106150",
        "realization": "realization_sloth_nom_cfe_pet_troute.json",
        "action": "run",
        "note": "USGS 09106150 is a NextGen gauge. No model was named. Chose CFE, PET, Noah-OWP, and t-route.",
    },
)
assert rejected_models["patch"]["gage"] == "09106150"
assert rejected_models["patch"]["realization"] == ""
assert rejected_models["patch"]["action"] == "do not run"
rejected_note = note_from_feedback(
    "USGS 09106150 is a NextGen gauge. No model was named. Chose CFE, PET, Noah-OWP, and t-route.",
    rejected_models["messages"],
)
assert "No model was named" not in rejected_note
assert "not supported in this repo for now" in rejected_note
assert interpret_realization(potomac)["source"] == "chosen"
summa = "Run a NextGen simulation for USGS gauge 09106150 using Summa, and report which components are actually supported."
summa_choice = interpret_realization(summa, ["Summa"])
assert summa_choice["source"] == "unsupported"
assert summa_choice["realization"] == ""
assert "Summa is a hydrologic model" in summa_choice["note"]
assert "not supported in this repo for now" in summa_choice["note"]
assert "No model was named" not in summa_choice["note"]
assert interpret_realization("Run a NextGen simulation for USGS gauge 09106150.", ["HBV"])["source"] == "unsupported"
assert interpret_realization("Simulate a watershed near Denver using the latest available historical data.")["source"] == "chosen"
bare_summa = "Run Summa for USGS gauge 09106150."
bare_choice = interpret_realization(bare_summa, ["Summa"])
assert bare_choice["source"] == "unsupported"
assert "Summa is a hydrologic model" in bare_choice["note"]
assert bare_choice["realization"] == ""
checked = review_plan(
    no_download,
    {
        "gage": "",
        "action": "do not run",
        "note": "01646500 is not a NextGen gauge, so not running.",
        "realization": "",
        "forcing": "NWM_RETRO_V3",
    },
)
assert checked["patch"]["gage"] == "01646500"
assert checked["patch"]["action"] == "run"
assert checked["patch"]["forcing"] == ""
assert checked["patch"]["nprocs"] == 4
assert checked["checks"]["check_gauge"]["message"] == "USGS 01646500 is a NextGen gauge."
assert "not a NextGen" not in note_from_feedback(checked["patch"].get("note", ""), checked["messages"])
assert "Forcing stays empty" in " ".join(checked["messages"])
still_unknown = restore_known_gage(
    {"gage": "", "action": "do not run", "note": "99999999 is not a NextGen gauge, so not running."},
    "Run NextGen for USGS gauge 99999999.",
)
assert still_unknown["gage"] == ""
assert "not a NextGen" in still_unknown["note"]
invented_folder = "Find the watershed upstream of USGS gauge 09106150, download the required HydroFabric and NWM retrospective forcing, generate the NextGen realization configuration, run a 7-day simulation in June 2020, and plot the resulting streamflow."
cleared_folder = review_plan(
    invented_folder,
    {"gage": "09106150", "outputDir": "nextgen_output/09106150_20200601_20200608", "action": "run"},
)
assert cleared_folder["patch"]["outputDir"] == ""
assert "user types the output folder" in agent_system_prompt()
assert "Rust and LSTM together are one model" in agent_system_prompt()
assert "Noah, Noah-OWP, and Noah-OWP-Modular are the same model" in agent_system_prompt()
rust_lstm = "Run a simulation using rust, lstm, without using the t-route model for the watershed upstream of USGS gauge 01646500."
rust_plan = review_plan(
    rust_lstm,
    {
        "gage": "01646500",
        "realization": "realization_rust_lstm.json",
        "action": "run",
        "models": ["rust", "lstm"],
    },
)
assert rust_plan["patch"]["realization"] == "realization_rust_lstm.json"
assert rust_plan["patch"]["action"] == "run"
assert "not supported" not in " ".join(rust_plan["messages"])
blank_file = review_plan(
    rust_lstm,
    {"gage": "01646500", "realization": "", "action": "run", "models": ["LSTM Rust"]},
)
assert blank_file["patch"]["realization"] == "realization_rust_lstm.json"
assert blank_file["patch"]["action"] == "run"
wrong_file = review_plan(
    rust_lstm,
    {"gage": "01646500", "realization": "realization_rust_lstm_troute.json", "action": "run", "models": ["LSTM Rust"]},
)
assert wrong_file["patch"]["realization"] == "realization_rust_lstm.json"
noah = review_plan(
    "Run a simulation using the Noah model for USGS gauge 01646500.",
    {
        "gage": "01646500",
        "realization": "realization_sloth_nom_cfe_pet.json",
        "action": "run",
        "models": ["Noah"],
    },
)
assert noah["patch"]["realization"] == "realization_sloth_nom_cfe_pet.json"
assert noah["patch"]["action"] == "run"
assert "not supported" not in " ".join(noah["messages"])
false_rust_note = note_from_feedback(
    "USGS 01646500 is a NextGen gauge. rust is a hydrologic model. It is not supported in this repo for now, so this run is not ready.",
    rust_plan["messages"],
)
assert "not supported" not in false_rust_note
assert "is a NextGen gauge" in false_rust_note
from datetime import datetime as _datetime
from nextgenhydro.forecast import plan_forecast

forecast_now = _datetime(2026, 10, 23, 19, 5)
day_forecast = plan_forecast("NWM_V3_MEDIUM_RANGE", "2026-10-24T00:00", "2026-10-25T00:00", forecast_now)
assert day_forecast["ok"] and day_forecast["forcing"] == "NWM_V3_MEDIUM_RANGE_12_1"
assert day_forecast["start"] == "2026-10-23T12:00" and day_forecast["end"] == "2026-10-25T00:00"
assert "240 hours" in day_forecast["message"]
switched = plan_forecast("NWM_V3_SHORT_RANGE", "2026-10-24T00:00", "2026-10-25T00:00", forecast_now)
assert switched["forcing"] == "NWM_V3_MEDIUM_RANGE_12_1" and "in place of short range" in switched["message"]
short = plan_forecast("NWM_V3_SHORT_RANGE", "2026-10-23T18:00", "2026-10-24T06:00", forecast_now)
assert short["ok"] and short["forcing"] == "NWM_V3_SHORT_RANGE_17" and short["start"] == "2026-10-23T17:00"
too_long = plan_forecast("NWM_V3_MEDIUM_RANGE", "2026-10-24T00:00", "2026-11-10T00:00", forecast_now)
assert not too_long["ok"] and "ends before the requested end" in too_long["message"]
too_old = plan_forecast("NWM_V3_MEDIUM_RANGE", "2026-08-01T00:00", "2026-08-02T00:00", forecast_now)
assert not too_old["ok"] and "30 days" in too_old["message"]
assert plan_forecast("NWM_RETRO_V3", "2020-06-01T00:00", "2020-06-02T00:00", forecast_now) is None
forecast_sentence = "Run a 24-hour NextGen streamflow forecast for the watershed upstream of USGS gauge 01646500, from October 24 to October 25, 2026."
forecast_review = review_plan(
    forecast_sentence,
    {"gage": "01646500", "start": "2026-10-24T00:00", "end": "2026-10-25T00:00", "forcing": "NWM_V3_MEDIUM_RANGE", "action": "run", "models": []},
    forecast_now,
)
assert forecast_review["patch"]["forcing"] == "NWM_V3_MEDIUM_RANGE_12_1"
assert forecast_review["patch"]["action"] == "run"
assert any("This is a forecast" in message for message in forecast_review["messages"])
forecast_command = datastream_command(
    {"gage": "01646500", "start": "2026-10-23T12:00", "end": "2026-10-25T00:00", "forcing": "NWM_V3_MEDIUM_RANGE_12_1"},
    {"outputDir": "./data/forecast", "realization": DEFAULT_REALIZATION, "nprocs": 4},
)
assert forecast_command["argv"][:4] == ["-s", "202610230000", "-e", "202610230000"]
assert forecast_command["ready"]
bare_command = datastream_command(
    {"gage": "01646500", "start": "2026-10-23T12:00", "end": "2026-10-25T00:00", "forcing": "NWM_V3_MEDIUM_RANGE"},
    {"outputDir": "./data/forecast", "realization": DEFAULT_REALIZATION, "nprocs": 4},
)
assert not bare_command["ready"]
assert "NWM_V3_MEDIUM_RANGE when it is longer" in agent_system_prompt()

print("python checks ok")
