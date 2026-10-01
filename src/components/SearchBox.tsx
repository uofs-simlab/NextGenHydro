import { useEffect, useState } from "react"
import type { PlaceHit } from "../types"

type SearchBoxProps = {
  onSelect: (place: PlaceHit) => void
}

type PhotonFeature = {
  geometry: { coordinates: [number, number] }
  properties: {
    name?: string
    city?: string
    state?: string
    country?: string
    osm_value?: string
  }
}

function zoomFor(kind: string | undefined): number {
  if (kind === "river" || kind === "stream") return 9
  if (kind === "state") return 6
  return 11
}

function parseCoordinates(text: string): PlaceHit | null {
  const match = text.trim().match(/^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/)
  if (!match) return null
  const lat = Number(match[1])
  const lng = Number(match[2])
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return { label: `${lat}, ${lng}`, detail: "Coordinates", lng, lat, zoom: 12 }
}

export function SearchBox({ onSelect }: SearchBoxProps) {
  const [query, setQuery] = useState("")
  const [hits, setHits] = useState<PlaceHit[]>([])
  const [status, setStatus] = useState("")

  useEffect(() => {
    const text = query.trim()
    if (text.length < 2) return
    const coordinates = parseCoordinates(text)
    if (coordinates) return
    const timer = window.setTimeout(() => {
      const url = `https://photon.komoot.io/api/?q=${encodeURIComponent(text)}&limit=6&lat=39.8&lon=-98.6`
      void fetch(url)
        .then((response) => response.json())
        .then((payload: { features?: PhotonFeature[] }) => {
          const next = (payload.features ?? [])
            .map((feature) => {
              const [lng, lat] = feature.geometry.coordinates
              const props = feature.properties
              const detail = [props.city, props.state, props.country].filter(Boolean).join(", ")
              return {
                label: props.name || detail || "Place",
                detail,
                lng,
                lat,
                zoom: zoomFor(props.osm_value),
              }
            })
            .filter((place) => place.label !== "Place" || place.detail)
          setHits(next)
          setStatus(next.length === 0 ? "No places found." : "")
        })
        .catch(() => {
          setHits([])
          setStatus("Search is unavailable.")
        })
    }, 280)
    return () => window.clearTimeout(timer)
  }, [query])

  const coordinates = parseCoordinates(query)
  const visible = query.trim().length < 2 ? [] : coordinates ? [coordinates] : hits
  const visibleStatus = query.trim().length < 2 ? "" : coordinates ? "" : status

  return (
    <form
      className="search"
      onSubmit={(event) => {
        event.preventDefault()
        if (visible[0]) {
          onSelect(visible[0])
          setQuery("")
          setHits([])
        }
      }}
    >
      <label className="search-label" htmlFor="map-search">
        Search the map
      </label>
      <input
        id="map-search"
        role="combobox"
        aria-expanded={visible.length > 0}
        aria-label="Search the map"
        placeholder="Town, river, or coordinates"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {(visible.length > 0 || visibleStatus) && (
        <ul className="search-results">
          {visibleStatus && <li className="search-status">{visibleStatus}</li>}
          {visible.map((place) => (
            <li key={`${place.label}-${place.lng}-${place.lat}`}>
              <button
                type="button"
                onClick={() => {
                  onSelect(place)
                  setQuery("")
                  setHits([])
                }}
              >
                {place.label}
                {place.detail && <small>{place.detail}</small>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
