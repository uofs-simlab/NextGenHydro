import { PALISADE_GAGE } from "../map/gageId.ts"
import { toDatastreamTime, type ParsedRequest } from "./parseRequest.ts"
import { outputDirFor, type RunOptions } from "./realizations.ts"

const PALISADE_GEOPACKAGE =
  "https://ciroh-community-ngen-datastream.s3.amazonaws.com/resources/v2.1_hydrofabric/geopackages/test_data/palisade.gpkg"

export type CommandPreview = {
  text: string
  argv: string[]
  ready: boolean
  note: string
}

function shellArg(value: string): string {
  if (/^[A-Za-z0-9_./:-]+$/.test(value)) return value
  return `'${value.replaceAll("'", `'\\''`)}'`
}

export function datastreamCommand(request: ParsedRequest, options: RunOptions): CommandPreview | null {
  const start = toDatastreamTime(request.start)
  const end = toDatastreamTime(request.end)
  const outputDir = outputDirFor(request.gage, options.outputDir)
  if (!request.gage || !start || !end || !outputDir) return null

  const argv = ["-s", start, "-e", end]
  if (request.forcing) argv.push("-C", request.forcing)
  argv.push("-d", outputDir)
  if (request.gage === PALISADE_GAGE) {
    argv.push("-g", PALISADE_GEOPACKAGE)
  } else {
    argv.push("-i", "hl", "-I", `Gages-${request.gage}`, "-v", "2.2")
  }
  argv.push("-R", `./configs/ngen/${options.realization}`)

  const lines = ["./scripts/datastream \\"]
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    const last = index + 2 >= argv.length
    lines.push(`  ${flag} ${shellArg(value ?? "")}${last ? "" : " \\"}`)
  }

  const datesOk = request.end > request.start
  const ready = datesOk && request.forcing !== ""
  let note = "Run starts this command in the datastreamcli folder."
  if (!datesOk) note = "The end is not after the start, so this command is not ready."
  else if (!request.forcing) note = "Forcing is still open, so this command is not ready."
  else if (request.gage === PALISADE_GAGE) {
    note = "Run starts this command in the datastreamcli folder. The geopackage is the Palisade hydrofabric on the map."
  } else {
    note = "Run starts this command in the datastreamcli folder. DataStreamCLI subsets hydrofabric 2.2 above this gage."
  }

  return { text: lines.join("\n"), argv, ready, note }
}
