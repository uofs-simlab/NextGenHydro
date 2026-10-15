# NextGenHydroNotes_UnderDevelopment

Notes for the app: the map, the request panel, the agent, and how a run is handed to DataStreamCLI. Continue new work in this folder.

## What the app does

The sentence box is the agent's input. **Ask** sends that sentence to the agent. **Run** is separate and starts DataStreamCLI on this computer. The agent does not start a run.

After **Ask**:

1. The sentence is read by `gpt-5-mini` when an OpenAI key is available. If the key is missing or the call fails, the local reader in `nextgenhydro/nlp.py` and `nextgenhydro/parse_request.py` does the same job, and the note says the model was not used.
2. The result is a new JSON plan. A new sentence does not keep a gage, dates, forcing, realization, or output folder from the previous sentence.
3. The plan keys are `location`, `gage`, `start`, `end`, `forcing`, `realization`, and `outputDir`.
4. A key stays empty when the sentence does not supply it, except the two choices below.
5. If the sentence names a place and no gage digits, the map lists the 5 nearest NextGen stations. Picking one fills `gage`.



## When the sentence does not name a model

A sentence that asks to run or simulate, and does not name CFE, Noah-OWP, LSTM, or t-route, still needs a realization. The agent chooses **CFE, PET, Noah-OWP, and t-route** (`realization_sloth_nom_cfe_pet_troute.json`).

A sentence that names a model keeps that stack. Noah-OWP, CFE, or PET without t-route uses `realization_sloth_nom_cfe_pet.json`. There is no CFE-only or Noah-OWP-only realization. (**For NOW**)

A sentence that says not to run, such as "do not run the simulation", leaves `realization` empty even if the word simulation appears. `outputDir` also stays empty unless the sentence names a folder.

## When the sentence does not name a forcing

These menu entries are National Water Model products DataStreamCLI downloads. They are not files already sitting in the repo.

| Forcing | Use |
|---|---|
| v3 retrospective | Historical reanalysis. Dates are used as written. This is the usual choice for a past year such as 2020. |
| v2 retrospective | The older reanalysis. |
| v3 short range | About an 18-hour operational forecast. Files last roughly 30 days. |
| v3 medium range | About a 10-day operational forecast. The last number in a name such as `NWM_V3_MEDIUM_RANGE_00_1` is one ensemble member: one forecast inside a set of forecasts that start from slightly different weather. |
| v3 analysis and assimilation | Recent analysis that includes observations. |
| v3 operational / NOMADS operational | Live feeds, not the historical archive. |

If the sentence names a forcing, that choice is kept. If it does not, and the dates are more than 45 days ago, the agent chooses **v3 retrospective**. The same choice is used when the sentence asks for historical data or the latest historical record and gives no dates. The note says so, and the Forcing field can be switched to v2 retrospective. If the sentence does not ask for historical data and has no dates, or the dates are recent enough for a forecast, forcing stays empty.

DataStreamCLI itself, when `-C` is omitted, also starts from `NWM_RETRO_V3` (`scripts/datastream`). This app does not omit `-C` once a forcing is set. It sends the forcing the agent or the form selected.

## Dates

Dates in the plan are `YYYY-MM-DDTHH:mm`, midnight when the sentence gives no clock. Forcing is hourly, so a time such as 23:59 is moved to that hour at 00 before DataStreamCLI starts.

A month name and a year, such as January 2020, is that whole month: start `2020-01-01T00:00`, end `2020-01-31T00:00`.

These writings are the same span, start `2020-07-01T00:00` and end `2020-07-07T00:00`:

- July 1–7, 2020
- 2020/July/01 , 2020/July/07
- 2020-July-01 - 2020-July-07
- 2020-07-01 - 2020-07-07
- 2020/07/01 - 2020/07/07
- 2020\07\01 - 2020\07\07
- the first week of July 2020

A comma between two dates is the same as a dash. Slashes, hyphens, and backslashes are the same separators. The second, third, and fourth weeks are days 8–14, 15–21, and 22–28.

## Location, gage, and stations

`location` is the place in the sentence. "A watershed in Colorado" has location Colorado. "Near Denver" has location Denver. "Bow River" has location Bow River. Picking a gage later does not replace that place.

When the sentence gives a gage and no place, `location` becomes the USGS station name, such as gage `01646500` becoming the Potomac station name. A river name is not a gage. `gage` stays empty until the sentence contains gage digits or the user picks a station.

A place with no gage digits lists the nearest stations that exist in hydrofabric 2.2. The first two are always kept. A later station is added only while it stays near that pair, and the list stops at the first far one. The cap is five. A USGS site that is missing from the hydrofabric, such as `05502100`, is not offered.

## Map and watershed

The map in `web/` is MapLibre in the browser. Every decision is Python in `nextgenhydro/`.

Hydrofabric 2.2 is the drainage network drawn on the map. National Water Model v3 retrospective is the weather forcing for a run. Changing the forcing does not change the basin outline.

For a gage other than Palisade, the blue shape is the land upstream of that gage, from `~/ngiab_preprocess_output/gage-<id>/config/gage-<id>_subset.gpkg`. The orange outlet is the point from the sentence or a map click. It sits on the gage only when that station is the point the basin drains to.

Palisade (`09106150`) uses the published geopackage for the run. The map does not draw a subset file for that gage.

An unfinished watershed file is not drawn, and the map does not fly to the ocean. If the finished file has no catchments, the map says so.

## US rivers and other domains

The ready-made path simulates US rivers. Hydrofabric 2.2 is the continental US NextGen network, an outlet is a USGS gage, and the weather is National Water Model forcing.

ngen itself can run another river if you supply a hydrofabric and forcings. DataStreamCLI can take your own geopackage (`-g`) and your own forcing files. Asking for the Bow River in this app cannot build that Canadian domain. The station list is USGS sites that are also in the NextGen hydrofabric.

Two US sentences that match this path:

```
Run a 24-hour NextGen simulation above USGS gage 09106150, from 20 June 2020 through 21 June 2020, using National Water Model retrospective forcing.
```

```
Run Noah-OWP above USGS gage 10154200 on the Provo River, from 1 May 2020 through 2 May 2020, using National Water Model retrospective forcing.
```

`09106150` is Palisade, Colorado. `10154200` is the Provo River near Woodland, Utah, the sample basin in the DataStreamCLI guide.

Example with no model and no forcing named. The agent fills both from the rules above:

```
Run a NextGen simulation for the watershed draining to USGS gage 01646500 from January 1, 2020, to January 10, 2020.
```

Example that prepares forcing and does not run. `realization` and `outputDir` stay empty. Gage, the first week of January 2021, and v3 retrospective are filled:

```
Prepare meteorological forcing for USGS gauge 01646500 for the first week of January 2021, but do not run the simulation.
```

## Output folder

DataStreamCLI will not write into a folder that already exists. A second run needs a new folder name.

The app does not invent `./data/gage-{id}`. Paths are relative to `NexGen/datastreamcli`, for example:

- `./data/palisade-june`
- `./data/palisade-june-2`

If the name is already on disk, the app stops before DataStreamCLI starts and asks for a new name. Known folders that cannot be reused include `./data/gage_01646500`, `./data/gage_03339000`, and `./data/gage_01491000`.

The live log is `logs/nextgenhydro.log` inside that folder. The app must not create the folder before DataStreamCLI checks that it is absent.

## Where the sentence rules live

`nextgenhydro/nlp.py` holds the realization and forcing choices, and `agent_system_prompt()` is the instruction text sent to the model. `nextgenhydro/parse_request.py` reads the gage and the dates. `nextgenhydro/agent.py` applies a new sentence onto a blank plan. `checks/test_core.py` checks those rules:

```bash
python3 checks/test_core.py
```

Current rules:

1. A named model selects that realization. An unnamed run or simulation selects CFE, PET, Noah-OWP, and t-route. A refusal to run leaves realization empty.
2. A named forcing is kept. Historical dates, or a request for historical data, select v3 retrospective.
3. A new sentence replaces the previous plan. A named month or week fills start and end. A place name stays in `location` after a gage is picked.
