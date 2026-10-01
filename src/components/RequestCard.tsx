import { useEffect, useRef, useState } from "react"
import { PALISADE_GAGE } from "../map/palisade"
import { datastreamCommand } from "../request/datastreamCommand"
import { FORCINGS, type ForcingId } from "../request/forcings"
import { toDatastreamTime, type ParsedRequest } from "../request/parseRequest"
import { REALIZATIONS, isRealizationId, outputDirFor, type RunOptions } from "../request/realizations"
import type { LngLat } from "../types"

type RequestCardProps = {
  request: ParsedRequest
  runOptions: RunOptions
  outlet: LngLat | null
  notice: string
  onChange: (request: ParsedRequest) => void
  onRunOptionsChange: (options: RunOptions) => void
  onClear: () => void
  onOutletChange: (outlet: LngLat | null) => void
}

function trimCoord(value: number): string {
  return String(Math.round(value * 1e6) / 1e6)
}

function parseCoord(text: string, min: number, max: number): number | null {
  const trimmed = text.trim()
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(trimmed)) return null
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < min || value > max) return null
  return value
}

function openFields(request: ParsedRequest): string[] {
  const open: string[] = []
  if (!request.gage) open.push("gage")
  if (!request.start) open.push("start")
  if (!request.end) open.push("end")
  if (!request.forcing) open.push("forcing")
  return open
}

function statusText(request: ParsedRequest, notice: string): string {
  if (notice) return notice
  if (request.start && request.end && request.end <= request.start) {
    return "The end is not after the start."
  }
  const open = openFields(request)
  if (open.length === 4) return "A sentence fills these fields. You can also type them."
  if (open.length === 0) return "The command is ready. Run starts DataStreamCLI on this computer."
  return `Still open: ${open.join(", ")}.`
}

export function RequestCard({
  request,
  runOptions,
  outlet,
  notice,
  onChange,
  onRunOptionsChange,
  onClear,
  onOutletChange,
}: RequestCardProps) {
  const [copied, setCopied] = useState(false)
  const [latText, setLatText] = useState("")
  const [lngText, setLngText] = useState("")
  const editingOutlet = useRef(false)
  const latTextRef = useRef("")
  const lngTextRef = useRef("")
  const startCode = toDatastreamTime(request.start)
  const endCode = toDatastreamTime(request.end)
  const preview = datastreamCommand(request, runOptions)
  const outputPlaceholder = outputDirFor(request.gage, "") || "./data/gage-09106150"
  const patch = (partial: Partial<ParsedRequest>) => onChange({ ...request, ...partial })
  useEffect(() => {
    if (editingOutlet.current) return
    const nextLat = outlet ? trimCoord(outlet.lat) : ""
    const nextLng = outlet ? trimCoord(outlet.lng) : ""
    latTextRef.current = nextLat
    lngTextRef.current = nextLng
    setLatText(nextLat)
    setLngText(nextLng)
  }, [outlet])

  const writeOutlet = (nextLat: string, nextLng: string) => {
    latTextRef.current = nextLat
    lngTextRef.current = nextLng
    setLatText(nextLat)
    setLngText(nextLng)
    if (nextLat.trim() === "" || nextLng.trim() === "") {
      onOutletChange(null)
      return
    }
    const lat = parseCoord(nextLat, -90, 90)
    const lng = parseCoord(nextLng, -180, 180)
    if (lat !== null && lng !== null) onOutletChange({ lat, lng })
  }

  const clearOutlet = () => {
    editingOutlet.current = false
    latTextRef.current = ""
    lngTextRef.current = ""
    setLatText("")
    setLngText("")
    onOutletChange(null)
  }

  const finishOutletEdit = () => {
    editingOutlet.current = false
    const lat = parseCoord(latTextRef.current, -90, 90)
    const lng = parseCoord(lngTextRef.current, -180, 180)
    if (latTextRef.current.trim() === "" && lngTextRef.current.trim() === "") {
      onOutletChange(null)
      return
    }
    if (lat === null || lng === null) {
      const nextLat = outlet ? trimCoord(outlet.lat) : ""
      const nextLng = outlet ? trimCoord(outlet.lng) : ""
      latTextRef.current = nextLat
      lngTextRef.current = nextLng
      setLatText(nextLat)
      setLngText(nextLng)
    }
  }

  const copyCommand = () => {
    if (!preview) return
    void navigator.clipboard.writeText(preview.text).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    })
  }

  return (
    <section className="request-card" aria-label="Run request">
      <div className="request-head">
        <p className="kicker">Run request</p>
        <button type="button" onClick={onClear}>
          Clear
        </button>
      </div>
      <p className="request-status">{statusText(request, notice)}</p>
      <label>
        USGS gage
        <input
          inputMode="numeric"
          aria-label="USGS gage"
          value={request.gage}
          placeholder="09106150"
          onChange={(event) => patch({ gage: event.target.value.replace(/[^\d]/g, "") })}
        />
      </label>
      <div
        className="outlet-fields"
        onFocus={() => {
          editingOutlet.current = true
        }}
        onBlur={(event) => {
          if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
          finishOutletEdit()
        }}
      >
        <div className="request-head">
          <p className="kicker">Outlet</p>
          <button type="button" onClick={clearOutlet} aria-label="Clear outlet">
            Clear
          </button>
        </div>
        <div className="outlet-pair">
          <label>
            Latitude
            <input
              aria-label="Outlet latitude"
              inputMode="decimal"
              value={latText}
              placeholder="39.0982"
              onChange={(event) => {
                const value = event.target.value
                const pair = value.match(/^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$/)
                const pastedLat = pair?.[1]
                const pastedLng = pair?.[2]
                if (pastedLat && pastedLng) writeOutlet(pastedLat, pastedLng)
                else writeOutlet(value, lngText)
              }}
            />
          </label>
          <label>
            Longitude
            <input
              aria-label="Outlet longitude"
              inputMode="decimal"
              value={lngText}
              placeholder="-108.3551"
              onChange={(event) => writeOutlet(latText, event.target.value)}
            />
          </label>
        </div>
      </div>
      <div className="request-dates">
        <label>
          Start
          <input
            type="datetime-local"
            aria-label="Start"
            value={request.start}
            onChange={(event) => patch({ start: event.target.value })}
          />
        </label>
        <label>
          End
          <input
            type="datetime-local"
            aria-label="End"
            value={request.end}
            onChange={(event) => patch({ end: event.target.value })}
          />
        </label>
      </div>
      {(startCode || endCode) && (
        <p className="request-code">
          DataStream times {startCode || "—"} to {endCode || "—"}
        </p>
      )}
      <label>
        Forcing
        <select
          aria-label="Forcing"
          value={request.forcing}
          onChange={(event) => patch({ forcing: event.target.value as ForcingId | "" })}
        >
          <option value="">Not named</option>
          {FORCINGS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Output folder
        <input
          aria-label="Output folder"
          value={runOptions.outputDir}
          placeholder={outputPlaceholder}
          spellCheck={false}
          onChange={(event) => onRunOptionsChange({ ...runOptions, outputDir: event.target.value })}
        />
      </label>
      <label>
        Realization
        <select
          aria-label="Realization"
          value={runOptions.realization}
          onChange={(event) => {
            const value = event.target.value
            if (isRealizationId(value)) onRunOptionsChange({ ...runOptions, realization: value })
          }}
        >
          {REALIZATIONS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      {request.gage !== "" && request.gage !== PALISADE_GAGE && (
        <p className="request-outlet">Catchment and river lines are drawn for USGS {PALISADE_GAGE} only.</p>
      )}
      {preview && (
        <div className="command-preview">
          <div className="request-head">
            <p className="kicker">DataStreamCLI</p>
            <button type="button" onClick={copyCommand}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre>
            <code>{preview.text}</code>
          </pre>
          <p className="request-outlet">{preview.note}</p>
        </div>
      )}
    </section>
  )
}
