import type { FeatureCollection } from "geojson"
import type { GeoJSONSource, Map } from "maplibre-gl"
import type { BasemapId } from "../types"

export { PALISADE_GAGE } from "./gageId.ts"

export const PALISADE_BOUNDS: [[number, number], [number, number]] = [
  [-108.68, 38.97],
  [-105.62, 40.49],
]

export type WatershedData = {
  divides: FeatureCollection
  flowlines: FeatureCollection
  gage: FeatureCollection
}

const DIVIDES = "divides"
const FLOWLINES = "flowlines"
const GAGE = "gage"

export async function loadWatershed(): Promise<WatershedData> {
  const [divides, flowlines, gage] = await Promise.all([
    fetch("/hydrofabric/divides.geojson").then((response) => response.json()),
    fetch("/hydrofabric/flowlines.geojson").then((response) => response.json()),
    fetch("/hydrofabric/gage.geojson").then((response) => response.json()),
  ])
  return { divides, flowlines, gage }
}

function colors(basemap: BasemapId) {
  if (basemap === "satellite") {
    return {
      fill: "rgba(214, 244, 246, 0.28)",
      edge: "#f7fffe",
      edgeOpacity: 0.95,
      river: "#b8f3fb",
    }
  }
  return {
    fill: "rgba(14, 92, 116, 0.34)",
    edge: "#083044",
    edgeOpacity: 0.85,
    river: "#042c3d",
  }
}

export function drawWatershed(map: Map, data: WatershedData, basemap: BasemapId, visible: boolean) {
  const paint = colors(basemap)
  const visibility = visible ? "visible" : "none"

  if (!map.getSource(DIVIDES)) {
    map.addSource(DIVIDES, { type: "geojson", data: data.divides })
    map.addLayer({
      id: "divides-fill",
      type: "fill",
      source: DIVIDES,
      layout: { visibility },
      paint: { "fill-color": paint.fill },
    })
    map.addLayer({
      id: "divides-line",
      type: "line",
      source: DIVIDES,
      layout: { visibility },
      paint: {
        "line-color": paint.edge,
        "line-opacity": paint.edgeOpacity,
        "line-width": 1.15,
      },
    })
  } else {
    ;(map.getSource(DIVIDES) as GeoJSONSource).setData(data.divides)
    map.setPaintProperty("divides-fill", "fill-color", paint.fill)
    map.setPaintProperty("divides-line", "line-color", paint.edge)
    map.setPaintProperty("divides-line", "line-opacity", paint.edgeOpacity)
  }

  if (!map.getSource(FLOWLINES)) {
    map.addSource(FLOWLINES, { type: "geojson", data: data.flowlines })
    map.addLayer({
      id: "flowlines",
      type: "line",
      source: FLOWLINES,
      layout: { visibility, "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": paint.river,
        "line-width": [
          "interpolate",
          ["linear"],
          ["coalesce", ["get", "stream_order"], 1],
          1,
          1.3,
          3,
          2.2,
          5,
          3.4,
          7,
          5.2,
        ],
      },
    })
  } else {
    ;(map.getSource(FLOWLINES) as GeoJSONSource).setData(data.flowlines)
    map.setPaintProperty("flowlines", "line-color", paint.river)
  }

  if (!map.getSource(GAGE)) {
    map.addSource(GAGE, { type: "geojson", data: data.gage })
    map.addLayer({
      id: "gage-point",
      type: "circle",
      source: GAGE,
      layout: { visibility },
      paint: {
        "circle-radius": 6,
        "circle-color": "#f6f3ec",
        "circle-stroke-width": 3,
        "circle-stroke-color": "#0d3342",
      },
    })
  }

  for (const id of ["divides-fill", "divides-line", "flowlines", "gage-point"]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visibility)
  }
}
