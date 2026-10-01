import assert from "node:assert/strict"
import { stationNameFromRdb } from "../src/request/siteName.ts"

const rdb = `# ---------------------------------- WARNING ----------------------------------------
#
agency_cd	site_no	station_nm
5s	15s	50s
USGS	09106150	COLO RIVER BELOW GRAND VALLEY DIV NR PALISADE, CO
`
assert.equal(stationNameFromRdb(rdb), "Colo River Below Grand Valley Div Nr Palisade, CO")
assert.equal(stationNameFromRdb("# no rows\n"), null)

console.log("siteName ok")
