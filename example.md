# First use

This page is for the first time you open NextGen Hydro. The app itself shows a JSON plan and a run form. Red fields mean a value is missing or wrong. **Run** stays off until the form is complete.

Install and start the app with [INSTALLATION.md](INSTALLATION.md). Then open `http://127.0.0.1:5180/`.

## What to do

1. Type a sentence and press **Ask**. The JSON plan and the form fill from that sentence.
2. If the sentence named a place and no gauge, pick a station on the map or from the list.
3. Type a new output folder, such as `./data/my-run`.
4. Open **Command** in the left sidebar if you want to see the DataStreamCLI command **Run** will start.
5. Press **Run**. Follow the work on **Live log**. Files appear on **Results**.

Example sentence:

```
Run a simulation for the watershed upstream of USGS gauge 01646500 from June 1 to June 7, 2021, using NWM retrospective forcing.
```

## How to read the JSON plan

The plan is the machine form of the sentence. A filled example looks like this:

```json
{
  "location": "Potomac River Near Wash, Dc Little Falls Pump Sta",
  "gauge": {
    "gauge number": "01646500",
    "gauge latitude": 38.94977778,
    "gauge longitude": -77.12763889
  },
  "outlet": {
    "outlet latitude": 38.94139,
    "outlet longitude": -77.12785
  },
  "start": "2021-06-01T00:00",
  "end": "2021-06-07T00:00",
  "forcing": "NWM_RETRO_V3",
  "realization": "realization_sloth_nom_cfe_pet_troute.json",
  "outputDir": "./data/my-run",
  "action": "run",
  "logging": "",
  "nprocs": 4,
  "note": "USGS 01646500 is a NextGen gauge."
}
```

In words, that plan is:

1. **Watershed.** Everything upstream of USGS 01646500 (Potomac River near Washington, DC). The map legend also shows catchment count and drainage area once the geopackage is drawn.
2. **Dates.** 1 June 2021 to 7 June 2021. Warm-up days start the simulation earlier so soil and groundwater settle. Retrospective runs default to 30 extra days. Set **Warm-up days** to 0 to skip.
3. **Weather input.** National Water Model v3 retrospective (February 1979 to January 2023). A forecast sentence uses short range (up to 18 hours) or medium range (longer).
4. **Models.** CFE, PET, Noah-OWP, and t-route. "Without t-route" picks the file that has no routing.
5. **Output folder.** A new folder under DataStreamCLI, for example `./data/my-run`. The run refuses a folder that already exists.
6. **Processes.** NextGen and forcingprocessor parallelize across processes. Use `-n` / `--NPROCS` to cap how many they use. Default is 4. The sentence can say 8 processes, 8 processors, 8 cores, 8 CPUs, 8 workers, 8 threads, 8 ranks, nprocs 8, process count 8, `-n 8`, `--NPROCS 8`, 8-way parallel, run in parallel on 8, parallelize with 8, or parallel computing with 8.
7. **Run.** Press **Run** when the red marks are gone.

The `note` line is what the agent or the local reader added, such as "USGS 01646500 is a NextGen gauge." **Copy** copies the full JSON.

If the sentence named a place and no gauge, `gauge number` stays empty until you pick a station. The map lists the nearest NextGen gauges.

## Before you can run

**Run** stays off while any form field is wrong. The field is marked in red. These are the checks:

| Field | When it stays red | What to do |
|---|---|---|
| USGS gauge | Empty, or not 7 to 15 digits | Type a gauge such as `01646500`, or **Ask** for a place and pick a station. |
| Start | Empty or not a real date | Choose a start. |
| End | Empty, not a real date, or not after Start | Choose an end after the start. |
| Forcing | Empty, or a forecast id with no cycle | Choose a forcing. For a forecast, **Ask** again so the app picks the newest cycle. |
| Dates vs archive | The window, including warm-up, is outside the forcing archive | NWM v3 retrospective covers 1979-02-01 to 2023-01-31 23:00 UTC. NWM v2 covers 1979-02-01 to 2019-12-31 23:00 UTC. Move the dates or change the forcing. |
| Dates vs forecast | The sentence asks for a forecast and the end is already in the past | A forecast covers upcoming hours. Use dates from now onward, or ask for a retrospective run. |
| Warm-up days | Not a whole number from 0 to 730, or used with a forecast | Use 0–730. Set 0 for a forecast. |
| Realization | Empty | Choose a realization. |
| Output folder | Empty, or a path with `..` or a line break | Type a new folder such as `./data/my-run`. |
| Evaluate | On, but the realization has no t-route, the dates are a forecast, or the action is a dry run | Evaluation needs t-route, retrospective dates, and a real run. |
| Action | The plan says `do not run` | Read the JSON `note`, fix the form or **Ask** again. |

Open **Command** to see the same readiness as a DataStreamCLI command. The server still refuses a second **Run** while one is going, and it refuses an output folder that already exists.
