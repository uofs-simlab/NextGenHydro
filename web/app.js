const state = {
  request: { gage: "", start: "", end: "", forcing: "" },
  realization: "",
  realizationSpecified: false,
  outputDir: "",
  outlet: null,
  gaugePoint: null,
  outletPoint: null,
  bindsGauge: true,
  planLocation: "",
  action: "",
  logging: "",
  nprocs: 4,
  note: "",
  gageOpen: true,
  outletOpen: true,
  gages: [],
  page: "map",
  runState: "idle",
  runOutput: "",
  runProblems: [],
  runCommand: null,
  runMessage: null,
  stopRequested: false,
  watershedPhase: "",
  watershedStats: null,
  warmupDays: 30,
  evaluate: false,
}

const $ = (id) => document.getElementById(id)
const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [10, 20],
  zoom: 1.6,
  minZoom: 1.5,
  renderWorldCopies: false,
})
map.addControl(new maplibregl.NavigationControl(), "top-right")
map.on("load", () => map.resize())
new ResizeObserver(() => map.resize()).observe($("map"))
let outletMarker = null
const gageMarkers = []
const pointPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 16, className: "point-tip", maxWidth: "280px" })
let gageHoverBound = false
let hydroOutlet = null
let hydroGageId = ""
let syncOutletFromFabric = false

function isoToLocal(value) {
  return value ? value.slice(0, 16) : ""
}
function localToIso(value) {
  return value ? value.slice(0, 16) : ""
}

function paintForm() {
  $("gage").value = state.request.gage
  $("start").value = isoToLocal(state.request.start)
  $("end").value = isoToLocal(state.request.end)
  showForcingOption(state.request.forcing)
  $("forcing").value = state.request.forcing
  $("realization").value = state.realization
  $("output").value = state.outputDir
  $("nprocs").value = String(state.nprocs)
  $("warmup").value = String(state.warmupDays)
  $("evaluate").checked = state.evaluate
  if ($("lat") && $("lng")) {
    $("lat").value = state.outlet ? state.outlet.lat : ""
    $("lng").value = state.outlet ? state.outlet.lng : ""
  }
  renderPlan()
  scheduleRunCheck()
}

function runBody() {
  return {
    gage: state.request.gage,
    start: state.request.start,
    end: state.request.end,
    forcing: state.request.forcing,
    realization: state.realization,
    outputDir: state.outputDir,
    action: state.action,
    logging: state.logging,
    nprocs: state.nprocs,
    warmupDays: state.warmupDays,
    evaluate: state.evaluate,
  }
}

let runCheckTimer = 0
let runCheckSerial = 0

function scheduleRunCheck() {
  window.clearTimeout(runCheckTimer)
  runCheckTimer = window.setTimeout(checkRun, 250)
}

async function checkRun() {
  window.clearTimeout(runCheckTimer)
  const serial = ++runCheckSerial
  try {
    const body = await fetch("/api/run/check", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(runBody()),
    }).then((response) => response.json())
    if (serial !== runCheckSerial) return
    state.runProblems = body.problems || []
    state.runCommand = body.command || null
  } catch {
    if (serial !== runCheckSerial) return
    state.runProblems = [{ field: "", message: "The app server did not answer. Is python3 app.py still running?" }]
    state.runCommand = null
  }
  paintRun()
}

function paintRun() {
  const running = state.runState === "running"
  const bad = new Set(state.runProblems.map((item) => item.field))
  for (const id of ["gage", "start", "end", "forcing", "realization", "output", "warmup"]) $(id).classList.toggle("is-invalid", bad.has(id))
  $("evaluate-row").classList.toggle("is-invalid", bad.has("evaluate"))
  $("run").disabled = running || state.runProblems.length > 0
  $("stop").disabled = !running || state.stopRequested
  if (state.page === "command") paintCommandPage()
  const box = $("message")
  box.replaceChildren()
  box.className = "message"
  if (state.runMessage) {
    box.classList.add(`is-${state.runMessage.kind}`)
    const text = document.createElement("p")
    text.textContent = state.runMessage.text
    box.append(text)
  }
  box.hidden = box.childElementCount === 0
  paintMarks()
}

function showForcingOption(id) {
  const select = $("forcing")
  if (!id || [...select.options].some((option) => option.value === id)) return
  const short = id.match(/^NWM_V3_SHORT_RANGE_(\d{2})$/)
  const medium = id.match(/^NWM_V3_MEDIUM_RANGE_(\d{2})_(\d)$/)
  const option = document.createElement("option")
  option.value = id
  option.textContent = short
    ? `National Water Model v3 short range, ${short[1]}Z cycle`
    : medium
      ? Number(medium[2]) === 0
        ? `National Water Model v3 medium range, ${medium[1]}Z cycle`
        : `National Water Model v3 medium range, ${medium[1]}Z cycle, member ${medium[2]}`
      : id
  select.append(option)
}

function samePoint(a, b) {
  return Boolean(a && b && Math.abs(a.lat - b.lat) < 1e-6 && Math.abs(a.lng - b.lng) < 1e-6)
}

function shownGauge() {
  if (state.gaugePoint && state.gaugePoint.lat != null && state.gaugePoint.lng != null) return state.gaugePoint
  return state.bindsGauge ? state.outlet : null
}

function shownOutlet() {
  if (state.outletPoint && state.outletPoint.lat != null && state.outletPoint.lng != null) return state.outletPoint
  return shownGauge()
}

function planText() {
  const gauge = shownGauge()
  const outlet = shownOutlet()
  return JSON.stringify({
    location: state.planLocation,
    gauge: {
      "gauge number": state.request.gage,
      "gauge latitude": gauge ? gauge.lat : null,
      "gauge longitude": gauge ? gauge.lng : null,
    },
    outlet: {
      "outlet latitude": outlet ? outlet.lat : null,
      "outlet longitude": outlet ? outlet.lng : null,
    },
    start: state.request.start,
    end: state.request.end,
    forcing: state.request.forcing,
    realization: state.realizationSpecified ? state.realization : "",
    outputDir: state.outputDir.trim(),
    action: state.action,
    logging: state.logging,
    nprocs: state.nprocs,
    warmupDays: state.warmupDays,
    evaluate: state.evaluate,
    note: state.note,
  }, null, 2)
}

function appendFold(plan, key, values, open, toggle) {
  const fold = document.createElement("button")
  fold.type = "button"
  fold.className = "gage-fold"
  fold.setAttribute("aria-expanded", open ? "true" : "false")
  fold.setAttribute("aria-label", key)
  fold.textContent = open ? `  "${key}": {` : `  "${key}": { … },`
  fold.addEventListener("click", toggle)
  plan.append(fold, "\n")
  if (!open) return
  const lines = Object.entries(values).map(([name, value]) => `    "${name}": ${JSON.stringify(value)}`)
  plan.append(`${lines.join(",\n")}\n  },\n`)
}

function renderPlan() {
  const fields = [
    ["location", state.planLocation],
    ["start", state.request.start],
    ["end", state.request.end],
    ["forcing", state.request.forcing],
    ["realization", state.realizationSpecified ? state.realization : ""],
    ["outputDir", state.outputDir.trim()],
    ["action", state.action],
    ["logging", state.logging],
    ["nprocs", state.nprocs],
    ["warmupDays", state.warmupDays],
    ["evaluate", state.evaluate],
    ["note", state.note],
  ]
  const gaugePoint = shownGauge()
  const outletPoint = shownOutlet()
  const gage = {
    "gauge number": state.request.gage,
    "gauge latitude": gaugePoint ? gaugePoint.lat : null,
    "gauge longitude": gaugePoint ? gaugePoint.lng : null,
  }
  const outlet = {
    "outlet latitude": outletPoint ? outletPoint.lat : null,
    "outlet longitude": outletPoint ? outletPoint.lng : null,
  }
  const plan = $("plan")
  plan.replaceChildren("{\n", `  "location": ${JSON.stringify(fields[0][1])},\n`)
  appendFold(plan, "gauge", gage, state.gageOpen, () => {
    state.gageOpen = !state.gageOpen
    renderPlan()
  })
  appendFold(plan, "outlet", outlet, state.outletOpen, () => {
    state.outletOpen = !state.outletOpen
    renderPlan()
  })
  fields.slice(1).forEach(([key, value], index, list) => {
    const comma = index < list.length - 1 ? "," : ""
    plan.append(`  "${key}": ${JSON.stringify(value)}${comma}\n`)
  })
  plan.append("}")
}

function shortDate(iso) {
  const date = new Date(`${iso}:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  const day = date.toLocaleDateString("en-US", { timeZone: "UTC", month: "long", day: "numeric", year: "numeric" })
  return iso.endsWith("T00:00") ? day : `${day} ${iso.slice(11)} UTC`
}

function statsText(stats) {
  const parts = [`${stats.catchments.toLocaleString("en-US")} catchments`]
  if (stats.areaKm2 != null) parts.push(`${Math.round(stats.areaKm2).toLocaleString("en-US")} km² drainage area`)
  return parts.join(", ")
}

function readForm() {
  state.request.gage = $("gage").value.trim()
  state.request.start = localToIso($("start").value)
  state.request.end = localToIso($("end").value)
  state.request.forcing = $("forcing").value
  state.realization = $("realization").value
  state.outputDir = $("output").value
  const nprocs = Number($("nprocs").value)
  state.nprocs = Number.isInteger(nprocs) && nprocs >= 1 ? Math.min(nprocs, 256) : 4
  const warmup = $("warmup").value.trim()
  state.warmupDays = /^\d+$/.test(warmup) ? Number(warmup) : warmup
  state.evaluate = $("evaluate").checked
  if ($("lat") && $("lng")) {
    const lat = Number($("lat").value)
    const lng = Number($("lng").value)
    state.outlet = Number.isFinite(lat) && Number.isFinite(lng) && $("lat").value !== "" ? { lat, lng } : null
  }
  if (state.bindsGauge) state.gaugePoint = state.outlet
  else state.outletPoint = state.outlet
  paintForm()
}

async function loadSetup() {
  const box = $("setup")
  let problems = []
  try {
    problems = (await fetch("/api/setup").then((response) => response.json())).problems || []
  } catch {
    problems = [{ message: "The app server did not answer the setup check.", fix: "Start it with python3 app.py.", blocking: true }]
  }
  box.replaceChildren()
  box.hidden = problems.length === 0
  if (!problems.length) return
  const heading = document.createElement("strong")
  heading.textContent = "Setup needs attention"
  box.append(heading)
  for (const item of problems) {
    const row = document.createElement("p")
    row.className = item.blocking ? "setup-row is-blocking" : "setup-row"
    row.textContent = `${item.message} Fix: ${item.fix}`
    box.append(row)
  }
}

async function loadCatalog() {
  const catalog = await fetch("/api/catalog").then((response) => response.json())
  $("forcing").replaceChildren(new Option("Not named", ""), ...catalog.forcings.map((item) => new Option(item.label, item.id)))
  $("realization").replaceChildren(...catalog.realizations.map((item) => new Option(item.label, item.id)))
  state.realization = catalog.defaultRealization
  const key = await fetch("/api/agent/key").then((response) => response.json())
  $("key-line").textContent = key.loaded ? "OpenAI key loaded." : "No OpenAI key yet. The local reader will fill what it can."
  paintForm()
}

function formatCoord(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return ""
  return String(Math.round(number * 1e8) / 1e8)
}

function pointTip(title, lines) {
  const root = document.createElement("div")
  const heading = document.createElement("strong")
  heading.textContent = title
  root.append(heading)
  for (const line of lines) {
    const row = document.createElement("p")
    row.textContent = line
    root.append(row)
  }
  return root
}

function showPointTip(lngLat, node) {
  pointPopup.setLngLat(lngLat).setDOMContent(node).addTo(map)
}

function hidePointTip() {
  pointPopup.remove()
}

function setOutlet(point) {
  if (outletMarker) outletMarker.remove()
  outletMarker = null
  hidePointTip()
  if (!point) return
  const element = document.createElement("div")
  element.className = "outlet-dot"
  const gage = state.request.gage
  const name = state.planLocation && state.planLocation !== `USGS ${gage}` ? state.planLocation : ""
  const lines = [
    gage ? `USGS ${gage}` : "",
    name,
    `Latitude ${formatCoord(point.lat)}`,
    `Longitude ${formatCoord(point.lng)}`,
    "USGS station position stored in the plan.",
  ].filter(Boolean)
  element.addEventListener("mouseenter", () => showPointTip([point.lng, point.lat], pointTip("USGS gauge", lines)))
  element.addEventListener("mouseleave", hidePointTip)
  outletMarker = new maplibregl.Marker({ element }).setLngLat([point.lng, point.lat]).addTo(map)
}

function setGages() {
  for (const marker of gageMarkers) marker.remove()
  gageMarkers.length = 0
  state.gages.forEach((gage, index) => {
    const element = document.createElement("button")
    element.className = gage.id === state.request.gage ? "gage-pin is-selected" : "gage-pin"
    element.textContent = String(index + 1)
    element.addEventListener("click", (event) => {
      event.stopPropagation()
      chooseGage(gage)
    })
    gageMarkers.push(new maplibregl.Marker({ element }).setLngLat([gage.lng, gage.lat]).addTo(map))
  })
  const box = $("gages")
  box.replaceChildren()
  state.gages.forEach((gage, index) => {
    const button = document.createElement("button")
    button.type = "button"
    button.className = "gage"
    const miles = Number.isFinite(gage.miles) ? ` ${gage.miles.toFixed(1)} mi` : ""
    button.textContent = `${index + 1} USGS ${gage.id} ${gage.name || ""}${miles}`
    button.addEventListener("click", () => chooseGage(gage))
    box.append(button)
  })
}

const WATERSHED_WAIT_MS = 10 * 60 * 1000
let watershedTimer = 0
let watershedSerial = 0

function clearWatershed() {
  window.clearTimeout(watershedTimer)
  watershedSerial += 1
  for (const id of ["gage-point", "flowlines", "divides"]) {
    if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(id)) map.removeSource(id)
  }
  hydroOutlet = null
  hydroGageId = ""
  state.watershedStats = null
  $("legend").hidden = true
  $("legend").textContent = ""
}

function drawWatershed(gage) {
  clearWatershed()
  if (!/^\d{7,15}$/.test(gage)) return
  const serial = watershedSerial
  const started = Date.now()
  $("legend").hidden = false
  $("legend").textContent = "Drawing the watershed."
  const poll = async () => {
    let response
    let body
    try {
      response = await fetch(`/api/watershed/geojson?gage=${gage}`)
      body = await response.json()
    } catch {
      if (serial === watershedSerial) $("legend").textContent = "The app server did not answer while drawing the watershed."
      return
    }
    if (serial !== watershedSerial || state.request.gage !== gage) return
    if (response.status === 202) {
      if (Date.now() - started > WATERSHED_WAIT_MS) {
        $("legend").textContent = "The watershed is taking longer than 10 minutes. Open the Watershed page to see its progress."
        return
      }
      $("legend").textContent = body.status || "Building the watershed."
      watershedTimer = window.setTimeout(poll, 2000)
      return
    }
    showWatershed(gage, response, body)
  }
  poll()
}

function showWatershed(gage, response, body) {
  const legend = $("legend")
  if (!response.ok) {
    legend.textContent = body.status || "The watershed could not be drawn."
    syncOutletFromFabric = false
    return
  }
  const picked = state.gages.find((item) => item.id === gage)
  const listed = picked && picked.name && picked.name !== `USGS ${gage}` ? picked.name : ""
  const name = listed || body.name || ""
  state.watershedStats = body.stats && body.stats.catchments ? { gage, ...body.stats } : null
  const size = state.watershedStats ? `\n${statsText(state.watershedStats)}` : ""
  legend.textContent = `USGS ${gage}${name ? `\n${name}` : ""}${size}\nCatchments  Rivers  Gauge`
  for (const id of ["divides", "flowlines", "gage-point"]) {
    if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(id)) map.removeSource(id)
  }
  map.addSource("divides", { type: "geojson", data: body.divides })
  map.addLayer({ id: "divides", type: "fill", source: "divides", paint: { "fill-color": "rgba(14, 92, 116, 0.34)" } })
  map.addSource("flowlines", { type: "geojson", data: body.flowlines })
  map.addLayer({ id: "flowlines", type: "line", source: "flowlines", paint: { "line-color": "#042c3d", "line-width": 1.4 } })
  const hydroFeature = (body.gage.features || [])[0]
  hydroOutlet = hydroFeature && hydroFeature.geometry ? hydroFeature.geometry.coordinates : null
  hydroGageId = (hydroFeature && hydroFeature.properties && hydroFeature.properties.id) || gage
  map.addSource("gage-point", { type: "geojson", data: body.gage })
  map.addLayer({ id: "gage-point", type: "circle", source: "gage-point", paint: { "circle-color": "#c45c26", "circle-radius": 6, "circle-stroke-width": 2, "circle-stroke-color": "#ffffff" } })
  if (!gageHoverBound) {
    gageHoverBound = true
    map.on("mouseenter", "gage-point", (event) => {
      const feature = event.features && event.features[0]
      const coordinates = hydroOutlet || (feature && feature.geometry && feature.geometry.coordinates)
      if (!coordinates) return
      map.getCanvas().style.cursor = "pointer"
      const [lng, lat] = coordinates
      const gageId = hydroGageId || (feature && feature.properties && feature.properties.id) || ""
      showPointTip(
        [lng, lat],
        pointTip("Hydrofabric outlet", [
          gageId ? `USGS ${gageId}` : "",
          `Latitude ${formatCoord(lat)}`,
          `Longitude ${formatCoord(lng)}`,
          "NextGen hydrofabric outlet. The catchments and rivers are built around this point.",
        ].filter(Boolean)),
      )
    })
    map.on("mouseleave", "gage-point", () => {
      map.getCanvas().style.cursor = ""
      hidePointTip()
    })
  }
  if (body.bounds) map.fitBounds(body.bounds, { padding: 48, maxZoom: 12 })
  useFabricOutlet(gage)
  refreshStatus()
}

function useFabricOutlet(gage) {
  if (!syncOutletFromFabric || state.request.gage !== gage) return
  syncOutletFromFabric = false
  if (!hydroOutlet) return
  const [lng, lat] = hydroOutlet
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return
  state.outletPoint = { lat, lng }
  state.bindsGauge = samePoint(state.gaugePoint, state.outletPoint)
  renderPlan()
}

function chooseGage(gage) {
  if (!gage) return
  state.request.gage = gage.id
  state.gaugePoint = { lat: gage.lat, lng: gage.lng }
  state.outletPoint = { lat: gage.lat, lng: gage.lng }
  state.bindsGauge = true
  state.outlet = { lat: gage.lat, lng: gage.lng }
  state.planLocation = gage.name || `USGS ${gage.id}`
  state.note = state.note
    .replace(/The nearest NextGen gauge is USGS \d+(?: \([^)]*\))?\.\s*/g, "")
    .replace(/The nearest NextGen stations are on the map\. Pick one to fill the gauge in the plan\.\s*/g, "")
    .replace(/You picked USGS \d+\.\s*/g, "")
    .trim()
  state.note = `${state.note} You picked USGS ${gage.id}.`.trim()
  syncOutletFromFabric = true
  paintForm()
  setGages()
  setOutlet(state.outlet)
  map.flyTo({ center: [gage.lng, gage.lat], zoom: 11 })
  drawWatershed(gage.id)
}

function liveLabel(runState) {
  if (runState === "running") return "Running"
  if (runState === "done") return "Finished"
  if (runState === "error") return "Failed"
  if (runState === "stopped") return "Stopped"
  return ""
}

function paintMarks() {
  const watershed = /^\d{7,15}$/.test(state.request.gage) ? watershedLabel(state.watershedPhase) : ""
  $("mark-watershed").textContent = watershed === "Waiting" ? "" : watershed
  $("mark-live").textContent = liveLabel(state.runState)
}

async function refreshStatus() {
  if (!/^\d{7,15}$/.test(state.request.gage)) {
    state.watershedPhase = ""
    paintMarks()
    return
  }
  const status = await fetch(`/api/watershed/status?gage=${state.request.gage}`).then((response) => response.json())
  state.watershedPhase = status.phase || ""
  paintMarks()
  if (state.page === "logs" || state.page === "live" || state.page === "results") loadPage(state.page)
}

let pageTimer = 0

function setMapInteractive(on) {
  for (const name of ["boxZoom", "dragPan", "dragRotate", "scrollZoom", "keyboard", "doubleClickZoom", "touchZoomRotate"]) {
    const handler = map[name]
    if (!handler) continue
    if (on) handler.enable()
    else handler.disable()
  }
}

function showStage(page) {
  const stage = $("stage")
  const workspace = $("workspace")
  const onMap = page === "map"
  stage.classList.toggle("show-page", !onMap)
  workspace.hidden = onMap
  setMapInteractive(onMap)
  if (onMap) map.resize()
}

function paintHydrograph(chart) {
  const box = $("page-chart")
  box.replaceChildren()
  const observed = (chart && chart.observed) || []
  const simulated = (chart && chart.simulated) || []
  if (!chart || (!observed.length && !simulated.length && !chart.scores)) {
    box.hidden = true
    return
  }
  box.hidden = false
  if (chart.scores) {
    const scores = document.createElement("dl")
    scores.className = "hydro-scores"
    for (const [label, key] of [["KGE", "kge"], ["NSE", "nse"], ["Relative bias", "relativeBias"]]) {
      if (chart.scores[key] == null) continue
      const dt = document.createElement("dt")
      const dd = document.createElement("dd")
      dt.textContent = label
      dd.textContent = String(chart.scores[key])
      scores.append(dt, dd)
    }
    box.append(scores)
  }
  const series = []
  if (observed.length) series.push({ name: "USGS observed", color: "#c45c26", points: observed })
  if (simulated.length) series.push({ name: "NextGen nexus", color: "#1a6b84", points: simulated })
  if (series.length) box.append(hydroSvg(series))
  const legend = document.createElement("p")
  legend.className = "hydro-legend"
  legend.textContent = series.map((item) => item.name).join("  ·  ")
  box.append(legend)
  if (chart.note) {
    const note = document.createElement("p")
    note.className = "hydro-note"
    note.textContent = chart.note
    box.append(note)
  }
}

function hydroSvg(series) {
  const width = 640
  const height = 220
  const pad = { left: 48, right: 12, top: 12, bottom: 28 }
  const points = series.flatMap((item) => item.points)
  const times = points.map((item) => new Date(`${item.t}:00Z`).getTime()).filter((value) => Number.isFinite(value))
  const values = points.map((item) => item.q).filter((value) => Number.isFinite(value))
  const minT = Math.min(...times)
  const maxT = Math.max(...times)
  const minQ = 0
  const maxQ = Math.max(...values, 0.01)
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const xOf = (t) => pad.left + ((new Date(`${t}:00Z`).getTime() - minT) / Math.max(maxT - minT, 1)) * innerW
  const yOf = (q) => pad.top + innerH - (q / maxQ) * innerH
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg")
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`)
  svg.setAttribute("role", "img")
  svg.setAttribute("aria-label", "Streamflow hydrograph")
  const axis = document.createElementNS("http://www.w3.org/2000/svg", "polyline")
  axis.setAttribute("fill", "none")
  axis.setAttribute("stroke", "rgba(255,255,255,0.25)")
  axis.setAttribute("points", `${pad.left},${pad.top} ${pad.left},${pad.top + innerH} ${pad.left + innerW},${pad.top + innerH}`)
  svg.append(axis)
  for (const item of series) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline")
    line.setAttribute("fill", "none")
    line.setAttribute("stroke", item.color)
    line.setAttribute("stroke-width", "2")
    line.setAttribute("points", item.points.map((point) => `${xOf(point.t).toFixed(1)},${yOf(point.q).toFixed(1)}`).join(" "))
    svg.append(line)
  }
  const peak = document.createElementNS("http://www.w3.org/2000/svg", "text")
  peak.setAttribute("x", "8")
  peak.setAttribute("y", "16")
  peak.setAttribute("fill", "#b8bcc8")
  peak.setAttribute("font-size", "11")
  peak.textContent = `${maxQ.toFixed(maxQ >= 10 ? 0 : 2)} m³/s`
  svg.append(peak)
  return svg
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function commandText() {
  if (!state.runCommand) return "Fill the form on the right. The DataStreamCLI command appears here when the run is ready."
  return `${state.runCommand.text}\n\n${state.runCommand.note}`
}

let logPointerDown = false

function pageBodyHasSelection() {
  const box = $("page-body")
  if (logPointerDown) return true
  if (typeof box.selectionStart === "number" && box.selectionStart !== box.selectionEnd) return true
  const pick = window.getSelection()
  if (!pick || pick.isCollapsed || !pick.rangeCount) return false
  return box.contains(pick.anchorNode) || box.contains(pick.focusNode)
}

function setPageBody(text) {
  const box = $("page-body")
  const next = text == null ? "" : String(text)
  const current = "value" in box ? box.value : box.textContent
  if (current === next) return
  if (next.startsWith(current) && current.length) {
    if ("value" in box && box.tagName === "TEXTAREA") {
      if (pageBodyHasSelection()) return
      box.value = next
      return
    }
    box.appendChild(document.createTextNode(next.slice(current.length)))
    return
  }
  if (pageBodyHasSelection()) return
  if ("value" in box && box.tagName === "TEXTAREA") box.value = next
  else box.textContent = next
}

function paintCommandPage() {
  $("page-title").textContent = "DataStreamCLI command"
  $("page-state").textContent = state.runCommand && !state.runProblems.length ? "Ready" : "Not ready"
  $("page-path").textContent = "This is the command Run starts in NexGen/datastreamcli."
  $("page-note").textContent = state.runProblems.length ? state.runProblems.map((item) => item.message).join(" ") : ""
  setPageBody(commandText())
  $("copy-command").hidden = false
}

function watershedLabel(phase) {
  if (phase === "preparing") return "Preparing"
  if (phase === "ready") return "Ready"
  if (phase === "failed") return "Failed"
  return "Waiting"
}

async function loadPage(page) {
  state.page = page
  for (const button of document.querySelectorAll(".nav button")) button.classList.toggle("is-on", button.dataset.page === page)
  showStage(page)
  window.clearInterval(pageTimer)
  if (page === "map") return
  const titles = { watershed: "Watershed", command: "DataStreamCLI command", logs: "Logs", results: "Results", live: "Live log" }
  $("page-title").textContent = titles[page] || page
  $("page-state").textContent = ""
  $("page-note").textContent = ""
  $("page-body").textContent = ""
  $("copy-command").hidden = !["command", "logs", "live"].includes(page)
  $("page-chart").hidden = true
  $("page-chart").replaceChildren()
  $("page-files").replaceChildren()
  if (page === "command") {
    paintCommandPage()
    return
  }
  const paint = async () => {
    if (state.page !== page) return
    const gage = state.request.gage
    const ready = /^\d{7,15}$/.test(gage)
    if (page === "watershed") {
      if (!ready) {
        $("page-path").textContent = "Set a USGS gauge to choose this path."
        setPageBody("")
        return
      }
      const status = await fetch(`/api/watershed/status?gage=${gage}`).then((response) => response.json())
      if (state.page !== page) return
      state.watershedPhase = status.phase || ""
      paintMarks()
      $("page-state").textContent = watershedLabel(status.phase)
      $("page-path").textContent = status.path || ""
      $("page-note").textContent = status.message || ""
      setPageBody(status.log || (status.phase === "preparing" ? "The watershed build output appears here." : ""))
      return
    }
    if (!ready || !state.outputDir) {
      $("page-path").textContent = "Set a USGS gauge and an output folder to choose this path."
      setPageBody(page === "results" ? "Result files appear in this folder after the run writes them." : "The log appears here after a run writes it.")
      return
    }
    const query = `gage=${encodeURIComponent(gage)}&outputDir=${encodeURIComponent(state.outputDir)}`
    if (page === "logs" || page === "live") {
      const path = page === "logs" ? "log" : "live"
      const body = await fetch(`/api/datastream/${path}?${query}`).then((response) => response.json())
      if (state.page !== page) return
      $("page-path").textContent = body.path || ""
      setPageBody(body.text || state.runOutput || (body.exists ? "The log is empty." : "The log appears here while DataStreamCLI writes it."))
    }
    if (page === "results") {
      const range = `start=${encodeURIComponent(state.request.start)}&end=${encodeURIComponent(state.request.end)}`
      const body = await fetch(`/api/datastream/result?${query}&${range}`).then((response) => response.json())
      if (state.page !== page) return
      $("page-path").textContent = body.path || ""
      $("page-body").textContent = ""
      paintHydrograph(body.hydrograph)
      const entries = body.entries || []
      $("page-files").replaceChildren(
        ...entries.map((entry) => {
          const row = document.createElement("li")
          const name = document.createElement("span")
          const size = document.createElement("span")
          name.textContent = entry.name
          size.textContent = formatBytes(entry.bytes)
          row.append(name, size)
          return row
        }),
      )
      if (!entries.length) $("page-body").textContent = "Result files appear in this folder after the run writes them."
    }
  }
  await paint()
  pageTimer = window.setInterval(paint, 2000)
}

function setAskStatus(text, kind = "busy") {
  const line = $("ask-status")
  line.hidden = !text
  line.textContent = text
  line.className = `ask-status is-${kind}`
}

function snapshotAsk() {
  return {
    gages: state.gages,
    outlet: state.outlet,
    request: { ...state.request },
    realization: state.realization,
    realizationSpecified: state.realizationSpecified,
    outputDir: state.outputDir,
    gaugePoint: state.gaugePoint,
    outletPoint: state.outletPoint,
    bindsGauge: state.bindsGauge,
    planLocation: state.planLocation,
    action: state.action,
    logging: state.logging,
    nprocs: state.nprocs,
    note: state.note,
    warmupDays: state.warmupDays,
    evaluate: state.evaluate,
  }
}

function restoreAfterFailedAsk(previous) {
  state.gages = previous.gages
  state.outlet = previous.outlet
  state.request = { ...previous.request }
  state.realization = previous.realization
  state.realizationSpecified = previous.realizationSpecified
  state.outputDir = previous.outputDir
  state.gaugePoint = previous.gaugePoint
  state.outletPoint = previous.outletPoint
  state.bindsGauge = previous.bindsGauge
  state.planLocation = previous.planLocation
  state.action = previous.action
  state.logging = previous.logging
  state.nprocs = previous.nprocs
  state.note = previous.note
  state.warmupDays = previous.warmupDays
  state.evaluate = previous.evaluate
  paintForm()
  setGages()
  setOutlet(previous.outlet)
  if (state.request.gage) drawWatershed(state.request.gage)
}

function clearForNewAsk() {
  clearWatershed()
  syncOutletFromFabric = false
  state.request = { gage: "", start: "", end: "", forcing: "" }
  state.realization = ""
  state.realizationSpecified = false
  state.outlet = null
  state.gaugePoint = null
  state.outletPoint = null
  state.bindsGauge = true
  state.planLocation = ""
  state.action = ""
  state.logging = ""
  state.nprocs = 4
  state.note = ""
  state.gages = []
  state.warmupDays = 30
  state.evaluate = false
  setGages()
  setOutlet(null)
  paintForm()
  if (state.runState !== "running") {
    state.runMessage = null
    state.runState = "idle"
  }
}

let askToken = 0

$("ask").addEventListener("click", async () => {
  const sentence = $("sentence").value.trim()
  if (!sentence) {
    setAskStatus("Write a sentence first, for example: Run USGS gauge 01646500 for June 1 to 7, 2021.", "error")
    return
  }
  const previous = snapshotAsk()
  const token = ++askToken
  $("ask").disabled = true
  clearForNewAsk()
  setAskStatus("Reading the sentence.")
  const slow = window.setTimeout(() => setAskStatus("Finding the place and nearby NextGen gauges. This can take 10 seconds."), 3000)
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        sentence,
        gage: "",
        start: "",
        end: "",
        forcing: "",
        realization: "",
        lat: null,
        lng: null,
        outputDir: previous.outputDir,
      }),
    })
    const body = await response.json()
    if (token !== askToken) return
    if (!response.ok || !body.request || !body.plan) {
      setAskStatus(body.note || `The server could not read that sentence (HTTP ${response.status}).`, "error")
      restoreAfterFailedAsk(previous)
      return
    }
    state.request = body.request
    state.realization = (body.runOptions && body.runOptions.realization) || ""
    state.realizationSpecified = Boolean(body.patch && body.patch.realization)
    state.outputDir = (body.runOptions && body.runOptions.outputDir) || previous.outputDir
    const gaugeFields = body.plan.gauge || {}
    const outletFields = body.plan.outlet || {}
    state.gaugePoint = gaugeFields["gauge latitude"] == null ? null : { lat: gaugeFields["gauge latitude"], lng: gaugeFields["gauge longitude"] }
    state.outletPoint = outletFields["outlet latitude"] == null ? null : { lat: outletFields["outlet latitude"], lng: outletFields["outlet longitude"] }
    state.bindsGauge = !state.outletPoint || samePoint(body.outlet, state.gaugePoint) || samePoint(state.outletPoint, state.gaugePoint)
    state.outlet = state.bindsGauge ? state.gaugePoint || body.outlet : state.outletPoint
    state.planLocation = body.plan.location
    state.action = body.plan.action || ""
    state.logging = body.plan.logging || ""
    state.nprocs = body.plan.nprocs || 4
    state.warmupDays = body.plan.warmupDays || 0
    state.evaluate = Boolean(body.plan.evaluate)
    state.note = body.plan.note || body.note || ""
    state.gages = body.gages || []
    paintForm()
    setOutlet(state.outlet)
    setGages()
    if (body.focus) {
      if (body.focus.bounds) map.fitBounds(body.focus.bounds, { padding: 64, maxZoom: 11 })
      else map.flyTo({ center: [body.focus.lng, body.focus.lat], zoom: body.focus.zoom })
    }
    if (state.request.gage) drawWatershed(state.request.gage)
    if (state.action === "do not run" && state.note) setAskStatus(state.note, "error")
    else setAskStatus("")
  } catch {
    if (token !== askToken) return
    setAskStatus("The app server did not answer. Is python3 app.py still running? The previous plan is unchanged.", "error")
    restoreAfterFailedAsk(previous)
  } finally {
    if (token === askToken) {
      window.clearTimeout(slow)
      $("ask").disabled = false
      paintRun()
    }
  }
})

function runOutcome() {
  const fix = state.runOutput.match(/^FIX: (.+)$/m)
  const exited = state.runOutput.match(/DataStreamCLI exited (-?\d+)\./)
  if (state.stopRequested) {
    return { runState: "stopped", message: { kind: "info", text: "Stopped. The output folder keeps what was written before Stop." } }
  }
  if (exited && exited[1] === "0") {
    return { runState: "done", message: { kind: "ok", text: "Finished. Open Results to see the files." } }
  }
  const start = state.runOutput.includes("DataStreamCLI was not started")
    ? "The watershed step failed, so DataStreamCLI did not start."
    : exited
      ? `DataStreamCLI stopped with exit code ${exited[1]}.`
      : "The run ended without a result. The connection to the app server may have closed."
  const tail = fix ? ` Fix: ${fix[1]}` : " Open the Live log to see the last step."
  return { runState: "error", message: { kind: "error", text: start + tail } }
}

$("run").addEventListener("click", async () => {
  if (state.runState === "running") return
  readForm()
  await checkRun()
  if (state.runProblems.length) return
  state.runState = "running"
  state.stopRequested = false
  state.runOutput = ""
  state.runMessage = { kind: "info", text: "Running. Open the Live log to follow each step." }
  paintRun()
  let response
  try {
    response = await fetch("/api/datastream/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(runBody()),
    })
  } catch {
    state.runState = "idle"
    state.runMessage = { kind: "error", text: "The app server did not answer. Is python3 app.py still running?" }
    paintRun()
    return
  }
  if (!response.ok) {
    const text = (await response.text()).trim()
    state.runState = "idle"
    state.runMessage = { kind: "error", text: text || `The server refused the run (HTTP ${response.status}).` }
    paintRun()
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  try {
    while (true) {
      const step = await reader.read()
      state.runOutput += decoder.decode(step.value || new Uint8Array(), { stream: !step.done })
      if (step.done) break
    }
  } catch {
    state.runOutput += "\nThe connection to the app server closed.\n"
  }
  const outcome = runOutcome()
  state.runState = outcome.runState
  state.runMessage = outcome.message
  state.stopRequested = false
  if (state.page === "live" || state.page === "logs") loadPage(state.page)
  paintRun()
  checkRun()
})

function copyWithFallback(text) {
  const box = document.createElement("textarea")
  box.value = text
  box.setAttribute("readonly", "")
  box.style.position = "fixed"
  box.style.top = "0"
  box.style.left = "0"
  box.style.opacity = "0"
  document.body.append(box)
  box.focus()
  box.select()
  let copied = false
  try {
    copied = document.execCommand("copy")
  } catch {
    copied = false
  }
  box.remove()
  return copied
}

$("page-body").addEventListener("pointerdown", (event) => {
  logPointerDown = true
  event.stopPropagation()
})
window.addEventListener("pointerup", () => {
  logPointerDown = false
})
window.addEventListener("pointercancel", () => {
  logPointerDown = false
})
$("workspace").addEventListener("selectstart", (event) => {
  event.stopPropagation()
})

$("copy-command").addEventListener("click", async () => {
  const text = state.page === "command" ? commandText() : $("page-body").textContent
  let copied = false
  try {
    await navigator.clipboard.writeText(text)
    copied = true
  } catch {
    copied = copyWithFallback(text)
  }
  const button = $("copy-command")
  button.textContent = copied ? "Copied" : "Copy"
  if (!copied) return
  setTimeout(() => {
    button.textContent = "Copy"
  }, 1400)
})

$("copy-plan").addEventListener("click", async () => {
  const text = planText()
  let copied = false
  try {
    await navigator.clipboard.writeText(text)
    copied = true
  } catch {
    copied = copyWithFallback(text)
  }
  const button = $("copy-plan")
  button.textContent = copied ? "Copied" : "Copy"
  if (!copied) return
  setTimeout(() => {
    button.textContent = "Copy"
  }, 1400)
})

$("stop").addEventListener("click", () => {
  if (state.runState !== "running") return
  state.stopRequested = true
  state.runMessage = { kind: "info", text: "Stopping. The status changes when DataStreamCLI has ended." }
  paintRun()
  fetch("/api/datastream/stop", { method: "POST" }).catch(() => {})
})
for (const id of ["gage", "start", "end", "forcing", "realization", "output", "nprocs", "warmup", "evaluate", "lat", "lng"]) {
  if (!$(id)) continue
  const changed = () => {
    if (id === "realization") state.realizationSpecified = true
    formEdited(id)
    if (id === "gage") refreshStatus()
  }
  $(id).addEventListener("change", changed)
  if ($(id).tagName === "INPUT") $(id).addEventListener("input", () => formEdited(id))
}

function formEdited(id) {
  if (state.runState !== "running") state.runMessage = null
  if (state.action === "do not run" && ["gage", "start", "end", "forcing", "realization"].includes(id)) state.action = "run"
  readForm()
}
for (const button of document.querySelectorAll(".nav button")) {
  button.addEventListener("click", () => loadPage(button.dataset.page))
}

function bindSideFolds() {
  const shell = document.querySelector(".shell")
  const foldNav = $("fold-nav")
  const foldPanel = $("fold-panel")
  const paint = () => {
    const navShut = shell.classList.contains("nav-collapsed")
    const panelShut = shell.classList.contains("panel-collapsed")
    foldNav.setAttribute("aria-expanded", String(!navShut))
    foldNav.setAttribute("aria-label", navShut ? "Expand the left sidebar" : "Shrink the left sidebar")
    foldNav.title = navShut ? "Expand the left sidebar" : "Shrink the left sidebar"
    foldNav.textContent = navShut ? "›" : "‹"
    foldPanel.setAttribute("aria-expanded", String(!panelShut))
    foldPanel.setAttribute("aria-label", panelShut ? "Expand the right sidebar" : "Shrink the right sidebar")
    foldPanel.title = panelShut ? "Expand the right sidebar" : "Shrink the right sidebar"
    foldPanel.textContent = panelShut ? "‹" : "›"
  }
  foldNav.addEventListener("click", () => {
    shell.classList.toggle("nav-collapsed")
    paint()
  })
  foldPanel.addEventListener("click", () => {
    shell.classList.toggle("panel-collapsed")
    paint()
  })
}
bindSideFolds()
loadCatalog()
loadSetup()
