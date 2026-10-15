# NextGenHydro Python

This is the Python copy of NextGenHydro. The TypeScript app on the Desktop is unchanged.

Start it from this folder:

```bash
python3 app.py
```

Then open http://127.0.0.1:5180/

The sentence reader, JSON plan, nearest NextGen stations, watershed file, and DataStreamCLI launch are Python modules in `nextgenhydro/`. The page in `web/` draws the map with MapLibre, because a browser map does not run as Python. It calls this server for every decision.

The OpenAI key is read from `.openai-key.local` in this folder, then from `NextGenHydro/.openai-key.local`, then from `OPENAI_API_KEY`. DataStreamCLI is the existing folder `NexGen/datastreamcli`.
