# Installation

Programs you need before NextGenHydro can start a DataStreamCLI run. Docker images are pulled on the first run. They are not separate installs.

The app expects these folders side by side on the Desktop:

- `NextGenHydro` — this app
- `your-path/datastreamcli` — DataStreamCLI

The app starts `your-path/datastreamcli/scripts/datastream` and writes output folders under that repo, for example `your-path/datastreamcli/data/my-run`.

## Required

| Program | Why it is needed |
|---|---|
| Python 3 | Runs this app (`python3 app.py`) and the small Python step inside DataStreamCLI. The standard library is enough. No pip install. The local address is `http://127.0.0.1:5180/`. |
| Git | Clones DataStreamCLI. |
| Docker Desktop | DataStreamCLI runs forcing, config generation, and ngen inside containers. Docker must be running before **Run**. The first run pulls `awiciroh/datastream`, the forcing-processor image, `awiciroh/ciroh-ngen-image` (NGIAB), and TEEHR. |
| curl | DataStreamCLI downloads the hydrofabric and other files with `curl`. macOS already includes it. |
| tar | Unpacks downloaded archives. macOS already includes it. |
| pigz | DataStreamCLI compresses the generated ngen configs with `pigz`. Install it if `pigz` is not on `PATH`. |
| uv | Provides `uvx`. On **Run**, a gage other than Palisade builds its watershed with `uvx ngiab-prep -i gage-<id> -s` before DataStreamCLI starts. Install uv from [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/). Confirm with `uvx --version`. |

Palisade (`09106150`) uses a published geopackage. Every other USGS gage uses the watershed file from [NGIAB Data Preprocess](https://github.com/CIROH-UA/NGIAB_data_preprocess), already cloned at `NexGen/NGIAB_data_preprocess`. The app runs only the subset step. Forcing stays with DataStreamCLI.

The geopackage is written to `~/ngiab_preprocess_output/gage-<id>/config/gage-<id>_subset.gpkg`. A later run for the same gage reuses that file. The first subset downloads hydrofabric 2.2 into `~/.ngiab/hydrofabric`. DataStreamCLI receives the file with `-g` and does not call `hfsubset`.


## Start the app

From `NextGenHydro`:

```bash
python3 app.py
```

Open `http://127.0.0.1:5180/`. **Ask** fills the plan. **Run** starts DataStreamCLI. The output folder must be a new name. DataStreamCLI refuses a folder that already exists.

## Not installed on the host

ngen, CFE, Noah-OWP, PET, SLOTH, LSTM, and t-route run inside the NGIAB container. National Water Model forcing is downloaded during the run. Those are not host installs. Node.js is not required for this copy. The page in `web/` is static files served by `app.py`.
