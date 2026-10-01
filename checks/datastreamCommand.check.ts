import assert from "node:assert/strict"
import { datastreamCommand } from "../src/request/datastreamCommand.ts"
import { DEFAULT_RUN_OPTIONS } from "../src/request/realizations.ts"

const palisade = datastreamCommand(
  {
    gage: "09106150",
    start: "2020-05-10T00:00",
    end: "2020-06-21T00:00",
    forcing: "NWM_RETRO_V3",
  },
  DEFAULT_RUN_OPTIONS,
)
assert.ok(palisade)
assert.equal(palisade.ready, true)
assert.deepEqual(palisade.argv.slice(0, 6), ["-s", "202005100000", "-e", "202006210000", "-C", "NWM_RETRO_V3"])
assert.ok(palisade.argv.includes("./data/gage-09106150"))
assert.ok(palisade.text.includes("palisade.gpkg"))
assert.equal(palisade.argv.includes("-I"), false)
assert.ok(palisade.text.includes("realization_sloth_nom_cfe_pet_troute.json"))

const custom = datastreamCommand(
  {
    gage: "09106150",
    start: "2020-05-10T00:00",
    end: "2020-06-21T00:00",
    forcing: "NWM_RETRO_V3",
  },
  { outputDir: "./data/my run", realization: "realization_rust_lstm.json" },
)
assert.ok(custom)
assert.ok(custom.text.includes("'./data/my run'"))
assert.ok(custom.argv.includes("./data/my run"))
assert.ok(custom.text.includes("realization_rust_lstm.json"))

const unnamed = datastreamCommand(
  { gage: "09106150", start: "2020-05-10T00:00", end: "2020-06-21T00:00", forcing: "" },
  DEFAULT_RUN_OPTIONS,
)
assert.ok(unnamed)
assert.equal(unnamed.ready, false)
assert.equal(unnamed.argv.includes("-C"), false)

const other = datastreamCommand(
  { gage: "06752260", start: "2020-05-10T00:00", end: "2020-06-21T00:00", forcing: "NWM_RETRO_V3" },
  DEFAULT_RUN_OPTIONS,
)
assert.ok(other)
assert.deepEqual(
  other.argv.filter((item) => ["-i", "hl", "-I", "Gages-06752260", "-v", "2.2"].includes(item) || item.startsWith("Gages-")),
  ["-i", "hl", "-I", "Gages-06752260", "-v", "2.2"],
)
assert.equal(other.argv.includes("-g"), false)

assert.equal(
  datastreamCommand({ gage: "", start: "2020-05-10T00:00", end: "2020-06-21T00:00", forcing: "NWM_RETRO_V3" }, DEFAULT_RUN_OPTIONS),
  null,
)

console.log("datastreamCommand ok")
