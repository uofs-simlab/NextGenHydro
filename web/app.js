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
  watershedPhase: "",
}

const $ = (id) => document.getElementById(id)
const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [0, 12],
  zoom: 1.4,
})
map.addControl(new maplibregl.NavigationControl(), "top-right")
let outletMarker = null
const gageMarkers = []
const pointPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 16, className: "point-tip", maxWidth: "280px" })
let gageHoverBound = false
let hydroOutlet = null
let hydroGageId = ""

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
  $("forcing").value = state.request.forcing
  $("realization").value = state.realization
  $("output").value = state.outputDir
  $("nprocs").value = String(state.nprocs)
  if ($("lat") && $("lng")) {
    $("lat").value = state.outlet ? state.outlet.lat : ""
    $("lng").value = state.outlet ? state.outlet.lng : ""
  }
  renderPlan()
  $("run").disabled = state.action === "do not run"
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
    note: state.note,
  }, null, 2)
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
  plan.replaceChildren("{\n", `  "location": ${JSON.stringify(fields[0][1])},`)
  const fold = document.createElement("button")
  fold.type = "button"
  fold.className = "gage-fold"
  fold.setAttribute("aria-expanded", state.gageOpen ? "true" : "false")
  fold.setAttribute("aria-label", "gauge")
  fold.textContent = state.gageOpen
    ? `  "gauge": {\n    "gauge number": ${JSON.stringify(gage["gauge number"])},\n    "gauge latitude": ${JSON.stringify(gage["gauge latitude"])},\n    "gauge longitude": ${JSON.stringify(gage["gauge longitude"])}\n  },`
    : `  "gauge": { … },`
  fold.addEventListener("click", () => {
    state.gageOpen = !state.gageOpen
    renderPlan()
  })
  plan.append(fold)
  const outletFold = document.createElement("button")
  outletFold.type = "button"
  outletFold.className = "gage-fold"
  outletFold.setAttribute("aria-expanded", state.outletOpen ? "true" : "false")
  outletFold.setAttribute("aria-label", "outlet")
  outletFold.textContent = state.outletOpen
    ? `  "outlet": {\n    "outlet latitude": ${JSON.stringify(outlet["outlet latitude"])},\n    "outlet longitude": ${JSON.stringify(outlet["outlet longitude"])}\n  },`
    : `  "outlet": { … },`
  outletFold.addEventListener("click", () => {
    state.outletOpen = !state.outletOpen
    renderPlan()
  })
  plan.append(outletFold)
  fields.slice(1).forEach(([key, value], index, list) => {
    const comma = index < list.length - 1 ? "," : ""
    plan.append(`  "${key}": ${JSON.stringify(value)}${comma}\n`)
  })
  plan.append("}")
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
  if ($("lat") && $("lng")) {
    const lat = Number($("lat").value)
    const lng = Number($("lng").value)
    state.outlet = Number.isFinite(lat) && Number.isFinite(lng) && $("lat").value !== "" ? { lat, lng } : null
  }
  if (state.bindsGauge) state.gaugePoint = state.outlet
  else state.outletPoint = state.outlet
  paintForm()
}

async function loadCatalog() {
  const catalog = await fetch("/api/catalog").then((response) => response.json())
  $("forcing").innerHTML = `<option value="">Not named</option>` + catalog.forcings.map((item) => `<option value="${item.id}">${item.label}</option>`).join("")
  $("realization").innerHTML = catalog.realizations.map((item) => `<option value="${item.id}">${item.label}</option>`).join("")
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
  box.innerHTML = state.gages
    .map(
      (gage, index) =>
        `<button type="button" class="gage" data-id="${gage.id}">${index + 1} USGS ${gage.id} ${gage.name} ${gage.miles} mi</button>`,
    )
    .join("")
  for (const button of box.querySelectorAll("button")) {
    button.addEventListener("click", () => chooseGage(state.gages.find((gage) => gage.id === button.dataset.id)))
  }
}

async function drawWatershed(gage) {
  const legend = $("legend")
  if (!/^\d{7,15}$/.test(gage)) {
    legend.hidden = true
    return
  }
  legend.hidden = false
  legend.textContent = "Drawing the watershed."
  const response = await fetch(`/api/watershed/geojson?gage=${gage}`)
  const body = await response.json()
  if (response.status === 202) {
    legend.textContent = body.status || "Building the watershed."
    setTimeout(() => drawWatershed(gage), 2000)
    return
  }
  if (!response.ok) {
    legend.textContent = body.status || "The watershed could not be drawn."
    return
  }
  const picked = state.gages.find((item) => item.id === gage)
  const listed = picked && picked.name && picked.name !== `USGS ${gage}` ? picked.name : ""
  const name = listed || body.name || ""
  legend.textContent = `USGS ${gage}${name ? `\n${name}` : ""}\nCatchments  Rivers  Gauge`
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
  refreshStatus()
}

function chooseGage(gage) {
  if (!gage) return
  state.request.gage = gage.id
  state.outlet = { lat: gage.lat, lng: gage.lng }
  if (!state.planLocation) state.planLocation = gage.name
  paintForm()
  setGages()
  setOutlet(state.outlet)
  map.flyTo({ center: [gage.lng, gage.lat], zoom: 11 })
  drawWatershed(gage.id)
}

function liveLabel(runState) {
  if (runState === "running") return "Running"
  if (runState === "done") return "Finished"
  if (runState === "error") return "Stopped"
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

function showStage(page) {
  const stage = $("stage")
  const workspace = $("workspace")
  const onMap = page === "map"
  stage.classList.toggle("show-page", !onMap)
  workspace.hidden = onMap
  if (onMap) map.resize()
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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
  const titles = { watershed: "Watershed", logs: "Logs", results: "Results", live: "Live log" }
  $("page-title").textContent = titles[page] || page
  $("page-state").textContent = ""
  $("page-note").textContent = ""
  $("page-body").textContent = ""
  $("page-files").innerHTML = ""
  const paint = async () => {
    if (state.page !== page) return
    const gage = state.request.gage
    const ready = /^\d{7,15}$/.test(gage)
    if (page === "watershed") {
      if (!ready) {
        $("page-path").textContent = "Set a USGS gauge to choose this path."
        $("page-body").textContent = ""
        return
      }
      const status = await fetch(`/api/watershed/status?gage=${gage}`).then((response) => response.json())
      if (state.page !== page) return
      state.watershedPhase = status.phase || ""
      paintMarks()
      $("page-state").textContent = watershedLabel(status.phase)
      $("page-path").textContent = status.path || ""
      $("page-note").textContent = status.message || ""
      $("page-body").textContent = status.log || (status.phase === "preparing" ? "The watershed build output appears here." : "")
      return
    }
    if (!ready || !state.outputDir) {
      $("page-path").textContent = "Set a USGS gauge and an output folder to choose this path."
      $("page-body").textContent = page === "results" ? "Result files appear in this folder after the run writes them." : "The log appears here after a run writes it."
      return
    }
    const query = `gage=${encodeURIComponent(gage)}&outputDir=${encodeURIComponent(state.outputDir)}`
    if (page === "logs" || page === "live") {
      const path = page === "logs" ? "log" : "live"
      const body = await fetch(`/api/datastream/${path}?${query}`).then((response) => response.json())
      if (state.page !== page) return
      $("page-path").textContent = body.path || ""
      $("page-body").textContent = body.text || state.runOutput || (body.exists ? "The log is empty." : "The log appears here while DataStreamCLI writes it.")
    }
    if (page === "results") {
      const body = await fetch(`/api/datastream/result?${query}`).then((response) => response.json())
      if (state.page !== page) return
      $("page-path").textContent = body.path || ""
      $("page-body").textContent = ""
      const entries = body.entries || []
      $("page-files").innerHTML = entries.length
        ? entries.map((entry) => `<li><span>${entry.name}</span><span>${formatBytes(entry.bytes)}</span></li>`).join("")
        : ""
      if (!entries.length) $("page-body").textContent = "Result files appear in this folder after the run writes them."
    }
  }
  await paint()
  pageTimer = window.setInterval(paint, 2000)
}

$("ask").addEventListener("click", async () => {
  readForm()
  $("ask").disabled = true
  state.note = "Reading the sentence."
  paintForm()
  try {
    const body = await fetch("/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        sentence: $("sentence").value,
        ...state.request,
        realization: state.realization,
        lat: state.outlet ? state.outlet.lat : null,
        lng: state.outlet ? state.outlet.lng : null,
        outputDir: state.outputDir,
      }),
    }).then((response) => response.json())
    state.request = body.request
    state.realization = body.runOptions.realization
    state.realizationSpecified = Boolean(body.patch.realization)
    state.outputDir = body.runOptions.outputDir
    const gaugeFields = (body.plan && body.plan.gauge) || {}
    const outletFields = (body.plan && body.plan.outlet) || {}
    state.gaugePoint = gaugeFields["gauge latitude"] == null ? null : { lat: gaugeFields["gauge latitude"], lng: gaugeFields["gauge longitude"] }
    state.outletPoint = outletFields["outlet latitude"] == null ? null : { lat: outletFields["outlet latitude"], lng: outletFields["outlet longitude"] }
    state.bindsGauge = !state.outletPoint || samePoint(body.outlet, state.gaugePoint) || samePoint(state.outletPoint, state.gaugePoint)
    state.outlet = state.bindsGauge ? state.gaugePoint || body.outlet : state.outletPoint
    state.planLocation = body.plan.location
    state.action = body.plan.action || ""
    state.logging = body.plan.logging || ""
    state.nprocs = body.plan.nprocs || 4
    state.note = body.plan.note || body.note || ""
    state.gages = body.gages || []
    paintForm()
    setOutlet(state.outlet)
    setGages()
    if (body.focus) {
      if (body.focus.bounds) map.fitBounds(body.focus.bounds, { padding: 48 })
      else map.flyTo({ center: [body.focus.lng, body.focus.lat], zoom: body.focus.zoom })
    }
    if (state.request.gage) drawWatershed(state.request.gage)
  } finally {
    $("ask").disabled = false
  }
})

$("run").addEventListener("click", async () => {
  if (state.action === "do not run") return
  readForm()
  state.runState = "running"
  state.runOutput = ""
  paintMarks()
  const response = await fetch("/api/datastream/run", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      gage: state.request.gage,
      start: state.request.start,
      end: state.request.end,
      forcing: state.request.forcing,
      realization: state.realization,
      outputDir: state.outputDir,
      action: state.action,
      logging: state.logging,
      nprocs: state.nprocs,
    }),
  })
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const step = await reader.read()
    state.runOutput += decoder.decode(step.value || new Uint8Array(), { stream: !step.done })
    if (step.done) break
  }
  const blocked = state.runOutput.includes("DataStreamCLI was not started")
  const exited = state.runOutput.match(/DataStreamCLI exited (\d+)\./)
  state.runState = response.ok && !blocked && (!exited || exited[1] === "0") ? "done" : "error"
  if (state.page === "live" || state.page === "logs") loadPage(state.page)
  paintMarks()
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
  state.runState = "error"
  paintMarks()
  fetch("/api/datastream/stop", { method: "POST" })
})
for (const id of ["gage", "start", "end", "forcing", "realization", "output", "nprocs", "lat", "lng"]) {
  if (!$(id)) continue
  $(id).addEventListener("change", () => {
    if (id === "realization") state.realizationSpecified = true
    readForm()
    if (id === "gage") refreshStatus()
  })
}
for (const button of document.querySelectorAll(".nav button")) {
  button.addEventListener("click", () => loadPage(button.dataset.page))
}
loadCatalog()
