# Installation

Programs you need before NextGenHydro can start a DataStreamCLI run. Docker images are pulled on the first run. They are not separate installs.

The app expects these folders side by side in the same parent folder, for example the Desktop:

- `NextGenHydro` — this app
- `NexGen/datastreamcli` — DataStreamCLI

The app looks for DataStreamCLI at `../NexGen/datastreamcli` next to `NextGenHydro`. It starts `NexGen/datastreamcli/scripts/datastream` and writes output folders under that repo, for example `NexGen/datastreamcli/data/my-run`.

## DataStreamCLI: use the uofs-simlab fork

Clone DataStreamCLI from the uofs-simlab fork and check out the `ngen-app-fixing` branch. Do not use the upstream CIROH-UA repo for this app.

```bash
mkdir -p NexGen
cd NexGen
git clone https://github.com/uofs-simlab/datastreamcli.git
cd datastreamcli
git checkout ngen-app-fixing
```

The branch is DataStreamCLI release `v1.7.2` plus fixes this app needs. Tested commit: `6d0c2cc` (October 1, 2026).

| Commit | What it fixes |
|---|---|
| `5f1c90f` | Writes the waterbody column name the geopackage has (`WaterbodyID` or `rl_NHDWaterbodyComID`) into the t-route config. |
| `6d0c2cc` | Does the same for the length column (`Length_m` or `length_m`) and the gage column (`gage`, `gages`, or `rl_gages`). |

Hydrofabric versions name these fields differently. Upstream DataStreamCLI writes one fixed set of names, so t-route routing can fail to find a column when the geopackage uses the other name.

Pinned images on that branch. The run script reads them from `versions.yml` and `versions_integrations.yml`:

| Image | Version |
|---|---|
| `awiciroh/datastream` | `1.7.2` |
| forcingprocessor | `2.3.0` |
| `awiciroh/ciroh-ngen-image` (NGIAB) | `v1.9.0` |
| TEEHR | `latest` |

Two fixes in `scripts/datastream` are not committed on the branch yet. A fresh clone does not have them:

- `-V True` (verbose) is applied after the flags are read, so verbose output works.
- When the final Merkle hashing step fails, the run prints a message and continues. The simulation outputs are already written at that point.

Commit and push those two fixes to `ngen-app-fixing` before handing the branch to a new user.

## Required

| Program | Why it is needed |
|---|---|
| Python 3 | Runs this app (`python3 app.py`) and the small Python step inside DataStreamCLI. The standard library is enough. No pip install. The local address is `http://127.0.0.1:5180/`. |
| Git | Clones DataStreamCLI. |
| Docker Desktop | DataStreamCLI runs forcing, config generation, and ngen inside containers. Docker must be running before **Run**. The first run pulls `awiciroh/datastream`, the forcing-processor image, `awiciroh/ciroh-ngen-image` (NGIAB), and TEEHR. |
| curl | DataStreamCLI downloads the hydrofabric and other files with `curl`. macOS already includes it. |
| tar | Unpacks downloaded archives. macOS already includes it. |
| pigz | DataStreamCLI compresses the generated ngen configs with `pigz`. Install it if `pigz` is not on `PATH`. |
| uv | Provides `uvx`. On **Run**, every USGS gage, including Palisade `09106150`, builds its watershed with `uvx ngiab-prep -i gage-<id> -s` before DataStreamCLI starts. Install uv from [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/). Confirm with `uvx --version`. |

Every USGS gage uses the watershed file from [NGIAB Data Preprocess](https://github.com/CIROH-UA/NGIAB_data_preprocess), already cloned at `NexGen/NGIAB_data_preprocess`. The app runs only the subset step. Forcing stays with DataStreamCLI.

The geopackage is written to `~/ngiab_preprocess_output/gage-<id>/config/gage-<id>_subset.gpkg`. A later run for the same gage reuses that file. The first subset downloads hydrofabric 2.2 into `~/.ngiab/hydrofabric`. DataStreamCLI receives the file with `-g` and does not call `hfsubset`.


## OpenAI key

The agent reads each sentence with the OpenAI model `gpt-5-mini`. The page has no field for the key. Put the key in a local file before you start the app.

From `NextGenHydro`, copy the template and replace its only line with your key:

```bash
cp .openai-key.local.example .openai-key.local
chmod 600 .openai-key.local
```

`.openai-key.local` must hold the key alone on one line, with no spaces. It sits next to `app.py` and is listed in `.gitignore`, so git never commits it. Do not put your key in `.openai-key.local.example`, which is committed.

You can also set the key in the terminal that starts the app:

```bash
export OPENAI_API_KEY='sk-...'
python3 app.py
```

The app uses `.openai-key.local` first and `OPENAI_API_KEY` only when that file is missing. After the page opens, the panel says **OpenAI key loaded.** When it says **No OpenAI key yet**, the app falls back to the local reader, which understands fewer sentences. For example, it does not catch "without t-route", seasons such as "summer 2019", or a year alone.

## Start the app

From `NextGenHydro`:

```bash
python3 app.py
```

Open `http://127.0.0.1:5180/`. **Ask** fills the plan. **Run** starts DataStreamCLI. The output folder must be a new name. DataStreamCLI refuses a folder that already exists.

## Not installed on the host

ngen, CFE, Noah-OWP, PET, SLOTH, LSTM, and t-route run inside the NGIAB container. National Water Model forcing is downloaded during the run. Those are not host installs. Node.js is not required for this copy. The page in `web/` is static files served by `app.py`.
