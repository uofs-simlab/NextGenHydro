export type LngLat = {
  lng: number
  lat: number
}

export type BasemapId = "light" | "terrain" | "satellite"

export type PlaceHit = {
  label: string
  detail: string
  lng: number
  lat: number
  zoom: number
}

export type FlyTarget = LngLat & {
  zoom: number
  token: number
}

export type ChatMessage = {
  id: string
  role: "user" | "note"
  text: string
}
