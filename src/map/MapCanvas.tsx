import { memo, useEffect, useRef } from "react"
import { Map, Marker, NavigationControl, ScaleControl, type MapMouseEvent } from "maplibre-gl"
import type { BasemapId, FlyTarget, LngLat } from "../types"
import { prefersReducedMotion } from "../format"
import { styleFor } from "./basemaps"
import { drawWatershed, loadWatershed, type WatershedData } from "./palisade"

const TERRAIN_SOURCE = "terrain-dem"
const WORLD_BOUNDS: [[number, number], [number, number]] = [
  [-168, -56],
  [178, 72],
]

type MapCanvasProps = {
  basemap: BasemapId
  outlet: LngLat | null
  flyTarget: FlyTarget | null
  showWatershed: boolean
  layout: "split" | "map"
  onPick: (point: LngLat) => void
}

function applyTerrain(map: Map, basemap: BasemapId) {
  if (basemap !== "terrain") return
  if (map.getSource(TERRAIN_SOURCE)) return
  map.addSource(TERRAIN_SOURCE, {
    type: "raster-dem",
    tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
    encoding: "terrarium",
    tileSize: 256,
    maxzoom: 15,
    attribution: "Elevation © AWS Terrain Tiles",
  })
  map.setTerrain({ source: TERRAIN_SOURCE, exaggeration: 1.15 })
}

export const MapCanvas = memo(function MapCanvas({
  basemap,
  outlet,
  flyTarget,
  showWatershed,
  layout,
  onPick,
}: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map | null>(null)
  const markerRef = useRef<Marker | null>(null)
  const onPickRef = useRef(onPick)
  const basemapRef = useRef(basemap)
  const showRef = useRef(showWatershed)
  const watershedRef = useRef<WatershedData | null>(null)
  const skipInitialStyle = useRef(true)

  useEffect(() => {
    onPickRef.current = onPick
    basemapRef.current = basemap
    showRef.current = showWatershed
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const initial = basemapRef.current
    const map = new Map({
      container,
      style: styleFor(initial),
      center: [0, 12],
      zoom: 1.4,
      pitch: 0,
      maxPitch: 60,
      renderWorldCopies: false,
    })

    map.addControl(new NavigationControl({ visualizePitch: true }), "bottom-right")
    map.addControl(new ScaleControl({ maxWidth: 110, unit: "imperial" }), "bottom-left")

    map.on("style.load", () => {
      applyTerrain(map, basemapRef.current)
      if (watershedRef.current) {
        drawWatershed(map, watershedRef.current, basemapRef.current, showRef.current)
      }
    })
    map.once("load", () => {
      const frame = () => {
        if (map.getContainer().clientWidth < 40) return false
        map.fitBounds(WORLD_BOUNDS, {
          padding: { top: 120, bottom: 64, left: 28, right: 28 },
          duration: 0,
          pitch: 0,
          maxZoom: 2,
        })
        return true
      }
      if (!frame()) map.once("resize", () => void frame())
    })
    map.on("click", (event: MapMouseEvent) => {
      onPickRef.current({ lng: event.lngLat.lng, lat: event.lngLat.lat })
    })

    mapRef.current = map
    void loadWatershed()
      .then((data) => {
        if (mapRef.current !== map) return
        watershedRef.current = data
        const place = () => {
          if (mapRef.current !== map || !watershedRef.current) return
          drawWatershed(map, watershedRef.current, basemapRef.current, showRef.current)
        }
        if (map.isStyleLoaded()) place()
        else map.once("style.load", place)
      })
      .catch((error: unknown) => {
        console.error(error)
        watershedRef.current = null
      })
    return () => {
      markerRef.current?.remove()
      markerRef.current = null
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    mapRef.current?.resize()
  }, [layout])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (skipInitialStyle.current) {
      skipInitialStyle.current = false
      return
    }
    if (map.getPitch() > 1) {
      map.easeTo({ pitch: 0, duration: prefersReducedMotion() ? 0 : 700 })
    }
    map.setStyle(styleFor(basemap))
  }, [basemap])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (!outlet) {
      markerRef.current?.remove()
      markerRef.current = null
      return
    }
    const lngLat: [number, number] = [outlet.lng, outlet.lat]
    if (!markerRef.current) {
      const element = document.createElement("div")
      element.className = "outlet-dot"
      element.setAttribute("aria-label", "Outlet")
      markerRef.current = new Marker({ element, anchor: "center" }).setLngLat(lngLat).addTo(map)
      return
    }
    markerRef.current.setLngLat(lngLat)
  }, [outlet])

  useEffect(() => {
    const map = mapRef.current
    const data = watershedRef.current
    if (!map || !data || !map.isStyleLoaded()) return
    drawWatershed(map, data, basemapRef.current, showWatershed)
  }, [showWatershed])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !flyTarget) return
    map.flyTo({
      center: [flyTarget.lng, flyTarget.lat],
      zoom: flyTarget.zoom,
      duration: prefersReducedMotion() ? 0 : 1300,
      essential: true,
    })
  }, [flyTarget])

  return <div ref={containerRef} className="map-root" />
})
