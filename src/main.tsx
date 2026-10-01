import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { setWorkerUrl } from "maplibre-gl"
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url"
import "maplibre-gl/dist/maplibre-gl.css"
import "./index.css"
import App from "./App.tsx"

setWorkerUrl(maplibreWorkerUrl)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
