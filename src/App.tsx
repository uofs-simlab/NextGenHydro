import { useEffect, useRef, useState } from "react"
import { ChatPanel } from "./components/ChatPanel"
import { SearchBox } from "./components/SearchBox"
import { MapCanvas } from "./map/MapCanvas"
import { BASEMAPS } from "./map/basemaps"
import { PALISADE_GAGE } from "./map/palisade"
import { EMPTY_REQUEST, mergeRequest, parseRequest, type ParsedRequest } from "./request/parseRequest"
import { DEFAULT_RUN_OPTIONS, type RunOptions } from "./request/realizations"
import { lookupStationName } from "./request/siteName"
import type { BasemapId, ChatMessage, FlyTarget, LngLat, PlaceHit } from "./types"

function nextId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function noteFor(parsed: ParsedRequest, merged: ParsedRequest): string {
  const found = [parsed.gage && "gage", parsed.start && "start", parsed.end && "end", parsed.forcing && "forcing"].filter(
    Boolean,
  )
  if (found.length === 0) {
    return "I could not read a gage, a date, or a forcing from that sentence. The fields are unchanged."
  }
  const stillOpen = [!merged.gage && "gage", !merged.start && "start", !merged.end && "end", !merged.forcing && "forcing"]
    .filter(Boolean)
    .join(", ")
  const read = `Read ${found.join(", ")} from that sentence.`
  return stillOpen ? `${read} Still open: ${stillOpen}.` : `${read} The request is complete.`
}

export default function App() {
  const [basemap, setBasemap] = useState<BasemapId>("light")
  const [outlet, setOutlet] = useState<LngLat | null>(null)
  const [flyTarget, setFlyTarget] = useState<FlyTarget | null>(null)
  const [chatOpen, setChatOpen] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [request, setRequest] = useState<ParsedRequest>(EMPTY_REQUEST)
  const [runOptions, setRunOptions] = useState<RunOptions>(DEFAULT_RUN_OPTIONS)
  const [notice, setNotice] = useState("")
  const [station, setStation] = useState<{ gage: string; name: string } | null>(null)
  const [runState, setRunState] = useState<"idle" | "running" | "done" | "error">("idle")
  const [runLog, setRunLog] = useState("")
  const [runControl, setRunControl] = useState<AbortController | null>(null)

  useEffect(() => {
    const gage = request.gage
    if (gage.length < 7) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void lookupStationName(gage, controller.signal)
        .then((name) => {
          if (name) setStation({ gage, name })
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return
        })
    }, 280)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [request.gage])

  const stationName = station && station.gage === request.gage ? station.name : null
  const showWatershed = request.gage === PALISADE_GAGE

  const readSentence = (text: string) => {
    const parsed = parseRequest(text)
    const merged = mergeRequest(request, parsed)
    setRequest(merged)
    setNotice("")
    setMessages((current) => [
      ...current,
      { id: nextId(), role: "user", text },
      { id: nextId(), role: "note", text: noteFor(parsed, merged) },
    ])
  }

  const logText = useRef("")
  const logTimer = useRef<number | null>(null)

  const flushLog = () => {
    if (logTimer.current !== null) {
      window.clearTimeout(logTimer.current)
      logTimer.current = null
    }
    setRunLog(logText.current)
  }

  const pushLog = (chunk: string) => {
    const next = logText.current + chunk
    logText.current = next.length > 80_000 ? next.slice(next.length - 80_000) : next
    if (logTimer.current !== null) return
    logTimer.current = window.setTimeout(flushLog, 250)
  }

  const stopRun = () => {
    runControl?.abort()
    void fetch("/api/datastream/stop", { method: "POST" })
  }

  const startRun = () => {
    if (runState === "running") return
    const controller = new AbortController()
    setRunControl(controller)
    setRunState("running")
    logText.current = ""
    flushLog()
    void fetch("/api/datastream/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...request, ...runOptions }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          const message = (await response.text()) || "DataStreamCLI did not start."
          logText.current = message
          flushLog()
          setRunState("error")
          return
        }
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        for (;;) {
          const chunk = await reader.read()
          if (chunk.done) break
          pushLog(decoder.decode(chunk.value, { stream: true }))
        }
        pushLog(decoder.decode())
        flushLog()
        setRunState("done")
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          flushLog()
          setRunState("idle")
          return
        }
        logText.current = error instanceof Error ? error.message : "DataStreamCLI did not start."
        flushLog()
        setRunState("error")
      })
  }

  const goTo = (place: PlaceHit) => {
    setFlyTarget({ lng: place.lng, lat: place.lat, zoom: place.zoom, token: Date.now() })
  }

  return (
    <main className={chatOpen ? "shell" : "shell map-only"}>
      <section className="map-stage" aria-label="Map">
        <MapCanvas
          basemap={basemap}
          outlet={outlet}
          flyTarget={flyTarget}
          showWatershed={showWatershed}
          layout={chatOpen ? "split" : "map"}
          onPick={setOutlet}
        />
        <header className="brand">
          <p className="brand-mark">NextGen Hydro</p>
          <SearchBox onSelect={goTo} />
        </header>
        <div className="basemap-switch" role="group" aria-label="Basemap">
          {BASEMAPS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={basemap === item.id}
              onClick={() => setBasemap(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {request.gage !== "" && (
          <section className="watershed-legend" aria-label="Watershed">
            <p className="kicker">Watershed</p>
            <h2>{stationName ?? `USGS ${request.gage}`}</h2>
            <p className="watershed-gage">USGS {request.gage}</p>
            {showWatershed ? (
              <ul>
                <li>
                  <span className="swatch swatch-catchment" /> Catchments
                </li>
                <li>
                  <span className="swatch swatch-river" /> Rivers
                </li>
                <li>
                  <span className="swatch swatch-gage" /> Gage
                </li>
              </ul>
            ) : (
              <p className="watershed-note">Catchment and river lines are drawn for USGS {PALISADE_GAGE}.</p>
            )}
          </section>
        )}
        {outlet && (
          <section className="outlet-card" aria-label="Outlet">
            <p className="kicker">Outlet</p>
            <p>
              {outlet.lat.toFixed(4)}, {outlet.lng.toFixed(4)}
            </p>
          </section>
        )}
      </section>
      <ChatPanel
        open={chatOpen}
        messages={messages}
        request={request}
        runOptions={runOptions}
        outlet={outlet}
        notice={notice}
        runState={runState}
        runLog={runLog}
        onToggle={() => setChatOpen((open) => !open)}
        onRead={readSentence}
        onRequestChange={(next) => {
          setRequest(next)
          setNotice("")
        }}
        onRunOptionsChange={setRunOptions}
        onRun={startRun}
        onStop={stopRun}
        onOutletChange={setOutlet}
        onClearRequest={() => {
          if (runState === "running") stopRun()
          setRequest(EMPTY_REQUEST)
          setRunOptions(DEFAULT_RUN_OPTIONS)
          setOutlet(null)
          setNotice("")
          setRunLog("")
          setRunState("idle")
        }}
      />
    </main>
  )
}
