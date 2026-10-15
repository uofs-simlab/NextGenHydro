const state = {
  request: { gage: "", start: "", end: "", forcing: "" },
  realization: "",
  realizationSpecified: false,
  outputDir: "",
  outlet: null,
  planLocation: "",
  gages: [],
  page: "map",
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
  $("lat").value = state.outlet ? state.outlet.lat : ""
  $("lng").value = state.outlet ? state.outlet.lng : ""
  $("plan").textContent = JSON.stringify(
    {
      location: state.planLocation,
      gage: state.request.gage,
      start: state.request.start,
      end: state.request.end,
      forcing: state.request.forcing,
      realization: state.realizationSpecified ? state.realization : "",
      outputDir: state.outputDir.trim(),
    },
    null,
    2,
  )
}

function readForm() {
  state.request.gage = $("gage").value.trim()
  state.request.start = localToIso($("start").value)
  state.request.end = localToIso($("end").value)
  state.request.forcing = $("forcing").value
  state.realization = $("realization").value
  state.outputDir = $("output").value
  const lat = Number($("lat").value)
  const lng = Number($("lng").value)
  state.outlet = Number.isFinite(lat) && Number.isFinite(lng) && $("lat").value !== "" ? { lat, lng } : null
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

function setOutlet(point) {
  if (outletMarker) outletMarker.remove()
  outletMarker = null
  if (!point) return
  const element = document.createElement("div")
  element.className = "outlet-dot"
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
  if (!/^\d{7,15}$/.test(gage) || gage === "09106150") {
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
  legend.textContent = `${picked ? picked.name : "USGS " + gage}\nUSGS ${gage}\nCatchments  Rivers  Gage`
  for (const id of ["divides", "flowlines", "gage-point"]) {
    if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(id)) map.removeSource(id)
  }
  map.addSource("divides", { type: "geojson", data: body.divides })
  map.addLayer({ id: "divides", type: "fill", source: "divides", paint: { "fill-color": "rgba(14, 92, 116, 0.34)" } })
  map.addSource("flowlines", { type: "geojson", data: body.flowlines })
  map.addLayer({ id: "flowlines", type: "line", source: "flowlines", paint: { "line-color": "#042c3d", "line-width": 1.4 } })
  map.addSource("gage-point", { type: "geojson", data: body.gage })
  map.addLayer({ id: "gage-point", type: "circle", source: "gage-point", paint: { "circle-color": "#c45c26", "circle-radius": 5 } })
  if (body.bounds) map.fitBounds(body.bounds, { padding: 48, maxZoom: 12 })
  refreshStatus()
}

function chooseGage(gage) {
  if (!gage) return
  state.request.gage = gage.id
  if (!state.planLocation) state.planLocation = gage.name
  paintForm()
  setGages()
  setOutlet(state.outlet)
  map.flyTo({ center: [gage.lng, gage.lat], zoom: 11 })
  drawWatershed(gage.id)
}

async function refreshStatus() {
  if (!/^\d{7,15}$/.test(state.request.gage)) {
    $("status").textContent = "Set a USGS gage to prepare a watershed."
    return
  }
  const status = await fetch(`/api/watershed/status?gage=${state.request.gage}`).then((response) => response.json())
  $("status").textContent = `${status.phase}\n${status.message}`
  if (state.page === "logs" || state.page === "live" || state.page === "results") loadPage(state.page)
}

async function loadPage(page) {
  state.page = page
  for (const button of document.querySelectorAll(".nav button")) button.classList.toggle("is-on", button.dataset.page === page)
  if (!state.outputDir || !state.request.gage) return
  const query = `gage=${encodeURIComponent(state.request.gage)}&outputDir=${encodeURIComponent(state.outputDir)}`
  if (page === "logs" || page === "live") {
    const path = page === "logs" ? "log" : "live"
    const body = await fetch(`/api/datastream/${path}?${query}`).then((response) => response.json())
    $("log").textContent = body.text || body.path || ""
  }
  if (page === "results") {
    const body = await fetch(`/api/datastream/result?${query}`).then((response) => response.json())
    $("log").textContent = (body.entries || []).map((entry) => `${entry.name}  ${entry.bytes}`).join("\n") || body.path
  }
}

$("ask").addEventListener("click", async () => {
  readForm()
  $("ask").disabled = true
  $("note").textContent = "Reading the sentence."
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
    state.outlet = body.outlet
    state.planLocation = body.plan.location
    state.gages = body.gages || []
    $("note").textContent = body.note || ""
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
  readForm()
  $("log").textContent = ""
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
    }),
  })
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const step = await reader.read()
    if (step.done) break
    $("log").textContent += decoder.decode(step.value)
  }
})

$("stop").addEventListener("click", () => fetch("/api/datastream/stop", { method: "POST" }))
for (const id of ["gage", "start", "end", "forcing", "realization", "output", "lat", "lng"]) {
  $(id).addEventListener("change", () => {
    if (id === "realization") state.realizationSpecified = true
    readForm()
  })
}
for (const button of document.querySelectorAll(".nav button")) {
  button.addEventListener("click", () => loadPage(button.dataset.page))
}
loadCatalog()
