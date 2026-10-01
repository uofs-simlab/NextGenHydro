import { useEffect, useRef, useState } from "react"
import { datastreamCommand } from "../request/datastreamCommand"
import type { ParsedRequest } from "../request/parseRequest"
import type { RunOptions } from "../request/realizations"
import type { ChatMessage, LngLat } from "../types"
import { RequestCard } from "./RequestCard"

const EXAMPLES = [
  "Run a 24-hour NextGen simulation above USGS gage 09106150, from 20 June 2020 through 21 June 2020, using National Water Model retrospective forcing.",
  "Delineate the watershed that drains to the outlet on the map.",
]

type ChatPanelProps = {
  open: boolean
  messages: ChatMessage[]
  request: ParsedRequest
  runOptions: RunOptions
  outlet: LngLat | null
  notice: string
  runState: "idle" | "running" | "done" | "error"
  runLog: string
  onToggle: () => void
  onRead: (text: string) => void
  onRequestChange: (request: ParsedRequest) => void
  onRunOptionsChange: (options: RunOptions) => void
  onRun: () => void
  onStop: () => void
  onClearRequest: () => void
  onOutletChange: (outlet: LngLat | null) => void
}

export function ChatPanel({
  open,
  messages,
  request,
  runOptions,
  outlet,
  notice,
  runState,
  runLog,
  onToggle,
  onRead,
  onRequestChange,
  onRunOptionsChange,
  onRun,
  onStop,
  onClearRequest,
  onOutletChange,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("")
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const followOutput = useRef(true)

  useEffect(() => {
    const list = listRef.current
    if (!list || !followOutput.current) return
    if (runLog === "" && messages.length === 0) return
    list.scrollTop = list.scrollHeight
  }, [messages, runLog, open])

  if (!open) {
    return (
      <button type="button" className="chat-toggle" onClick={onToggle}>
        Ask
      </button>
    )
  }

  const preview = datastreamCommand(request, runOptions)
  const send = () => {
    const text = draft.trim()
    if (!text) return
    onRead(text)
    setDraft("")
  }

  return (
    <aside className="chat" aria-label="Simulation request">
      <header className="chat-header">
        <div>
          <p className="kicker">Request</p>
          <h2>Ask for a simulation</h2>
        </div>
        <button type="button" className="icon-button" onClick={onToggle} aria-label="Hide the request panel">
          <span aria-hidden="true">›</span>
        </button>
      </header>
      <p className="chat-lead">
        Write a run in a sentence. This step reads the gage, the dates, and the forcing, then writes the DataStreamCLI
        command. Run starts that command on this computer.
      </p>
      <div
        className="chat-scroll"
        ref={listRef}
        onScroll={(event) => {
          const box = event.currentTarget
          followOutput.current = box.scrollHeight - box.scrollTop - box.clientHeight < 48
        }}
      >
      <div className="chat-log">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>Start from a sentence, then edit it.</p>
            <div className="examples">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => {
                    setDraft(example)
                    inputRef.current?.focus()
                  }}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <article key={message.id} className={`bubble bubble-${message.role}`}>
              {message.text}
            </article>
          ))
        )}
      </div>
      <RequestCard
        request={request}
        runOptions={runOptions}
        outlet={outlet}
        notice={notice}
        onChange={onRequestChange}
        onRunOptionsChange={onRunOptionsChange}
        onClear={onClearRequest}
        onOutletChange={onOutletChange}
      />
      <section className="run-output" aria-label="Run output">
        {runLog === "" ? (
          <p className="run-output-empty">Run output shows here. Scroll this panel to read it.</p>
        ) : (
          <pre className="run-log">{runLog}</pre>
        )}
      </section>
      </div>
      <div className="run-bar">
        <button type="button" className="run-button" disabled={!preview?.ready || runState === "running"} onClick={onRun}>
          Run
        </button>
        {runState === "running" && (
          <button type="button" onClick={onStop}>
            Stop
          </button>
        )}
      </div>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          send()
        }}
      >
        <textarea
          ref={inputRef}
          rows={3}
          value={draft}
          placeholder="Describe the watershed, the dates, and the forcing."
          aria-label="Describe the watershed, the dates, and the forcing."
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              send()
            }
          }}
        />
        <div className="composer-row">
          <span>Enter to read the request</span>
          <button type="submit" disabled={!draft.trim()}>
            Read
          </button>
        </div>
      </form>
    </aside>
  )
}
