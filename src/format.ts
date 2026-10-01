import type { LngLat } from "./types"

export function formatLngLat(point: LngLat): string {
  const ns = point.lat >= 0 ? "N" : "S"
  const ew = point.lng >= 0 ? "E" : "W"
  return `${Math.abs(point.lat).toFixed(4)}° ${ns}, ${Math.abs(point.lng).toFixed(4)}° ${ew}`
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}
