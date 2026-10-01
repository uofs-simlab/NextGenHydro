import assert from "node:assert/strict"
import { mergeRequest, parseRequest } from "../src/request/parseRequest.ts"

const palisade = parseRequest(
  "Run a 24-hour NextGen simulation above USGS gage 09106150, from 20 June 2020 through 21 June 2020, using National Water Model retrospective forcing.",
)
assert.deepEqual(palisade, {
  gage: "09106150",
  start: "2020-06-20T00:00",
  end: "2020-06-21T00:00",
  forcing: "NWM_RETRO_V3",
})

const compact = parseRequest("gage 09106150 from 202006200100 to 202006210000 with NWM_RETRO_V2")
assert.equal(compact.start, "2020-06-20T01:00")
assert.equal(compact.end, "2020-06-21T00:00")
assert.equal(compact.forcing, "NWM_RETRO_V2")

const hours = parseRequest(
  "Run a 20-hour NextGen simulation above USGS gage 09106150, from 20 June 2020 through 21 June 2020, using National Water Model retrospective forcing.",
)
assert.equal(hours.start, "2020-06-20T00:00")
assert.equal(hours.end, "2020-06-20T20:00")

const shortRange = parseRequest("24-hour run starting June 20, 2020 using short-range forcing")
assert.equal(shortRange.start, "2020-06-20T00:00")
assert.equal(shortRange.end, "2020-06-21T00:00")
assert.equal(shortRange.forcing, "NWM_V3_SHORT_RANGE")

const delineate = parseRequest("Delineate the watershed that drains to the outlet on the map.")
assert.deepEqual(delineate, { gage: "", start: "", end: "", forcing: "" })

assert.equal(parseRequest("USGS 09106150").gage, "09106150")

const unnamed = parseRequest("Run NextGen above USGS gage 09106150, from 10 May 2020 through 21 June 2020,")
assert.equal(unnamed.forcing, "")
assert.equal(unnamed.start, "2020-05-10T00:00")
assert.equal(unnamed.end, "2020-06-21T00:00")
const cleared = mergeRequest(
  { gage: "09106150", start: "2020-06-20T00:00", end: "2020-06-21T00:00", forcing: "NWM_RETRO_V3" },
  unnamed,
)
assert.equal(cleared.forcing, "")
assert.equal(cleared.gage, "09106150")

const clock = parseRequest("from 20 June 2020 at 1:00 pm through 21 June 2020 at 1:00 am")
assert.equal(clock.start, "2020-06-20T13:00")
assert.equal(clock.end, "2020-06-21T01:00")

console.log("parseRequest ok")
