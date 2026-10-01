import type { StyleSpecification } from "maplibre-gl"
import type { BasemapId } from "../types"

const ESRI_IMAGERY =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

const ESRI_PLACES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"

const satelliteStyle: StyleSpecification = {
  version: 8,
  sources: {
    imagery: {
      type: "raster",
      tiles: [ESRI_IMAGERY],
      tileSize: 256,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    },
    places: {
      type: "raster",
      tiles: [ESRI_PLACES],
      tileSize: 256,
      attribution: "Place labels © Esri",
    },
  },
  layers: [
    { id: "imagery", type: "raster", source: "imagery" },
    { id: "places", type: "raster", source: "places" },
  ],
}

export function styleFor(basemap: BasemapId): string | StyleSpecification {
  if (basemap === "light") return "https://tiles.openfreemap.org/styles/positron"
  if (basemap === "terrain") return "https://tiles.openfreemap.org/styles/liberty"
  return satelliteStyle
}

export const BASEMAPS: { id: BasemapId; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "terrain", label: "Terrain" },
  { id: "satellite", label: "Satellite" },
]
