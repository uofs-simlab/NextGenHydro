import { spawn, type ChildProcess } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import type { Connect, Plugin, ViteDevServer } from "vite"
import { defineConfig } from "vite"
import { datastreamCommand } from "./src/request/datastreamCommand.ts"
import type { ParsedRequest } from "./src/request/parseRequest.ts"
import { isRealizationId, type RealizationId } from "./src/request/realizations.ts"

const DATASTREAM_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../NexGen/datastreamcli")
const SCRIPT = resolve(DATASTREAM_ROOT, "scripts/datastream")
const FORCINGS = new Set([
  "NWM_RETRO_V3",
  "NWM_RETRO_V2",
  "NWM_OPERATIONAL_V3",
  "NOMADS_OPERATIONAL",
  "NWM_V3_SHORT_RANGE",
  "NWM_V3_MEDIUM_RANGE",
  "NWM_V3_ANALYSIS_ASSIM",
])

let running: ChildProcess | null = null

function readBody(req: Connect.IncomingMessage): Promise<string> {
  return new Promise((resolveBody, reject) => {
    const chunks: Buffer[] = []
    let size = 0
    req.on("data", (chunk: Buffer) => {
      size += chunk.length
      if (size > 20_000) {
        reject(new Error("too large"))
        req.destroy()
        return
      }
      chunks.push(chunk)
    })
    req.on("end", () => resolveBody(Buffer.concat(chunks).toString("utf8")))
    req.on("error", reject)
  })
}

function datastreamApi(): Plugin {
  return {
    name: "datastream-api",
    configureServer(server: ViteDevServer) {
      server.middlewares.use(async (req, res, next) => {
        const url = req.url ?? ""
        if (req.method === "POST" && url === "/api/datastream/stop") {
          if (running && running.exitCode === null && !running.killed) running.kill("SIGTERM")
          res.statusCode = 200
          res.setHeader("content-type", "text/plain; charset=utf-8")
          res.end("Stopped.\n")
          return
        }
        if (req.method !== "POST" || url !== "/api/datastream/run") {
          next()
          return
        }
        if (running && running.exitCode === null && !running.killed) {
          res.statusCode = 409
          res.end("A DataStreamCLI run is already going.\n")
          return
        }
        let body: {
          gage?: string
          start?: string
          end?: string
          forcing?: string
          outputDir?: string
          realization?: string
        }
        try {
          body = JSON.parse(await readBody(req)) as typeof body
        } catch {
          res.statusCode = 400
          res.end("The run request is incomplete.\n")
          return
        }
        const gage = body.gage ?? ""
        const forcing = body.forcing ?? ""
        const realization = body.realization ?? ""
        const outputDir = body.outputDir ?? ""
        if (
          !/^\d{7,15}$/.test(gage) ||
          !body.start ||
          !body.end ||
          (forcing !== "" && !FORCINGS.has(forcing)) ||
          !isRealizationId(realization) ||
          /[\0\r\n]/.test(outputDir)
        ) {
          res.statusCode = 400
          res.end("The run request is incomplete.\n")
          return
        }
        const request: ParsedRequest = {
          gage,
          start: body.start,
          end: body.end,
          forcing: forcing as ParsedRequest["forcing"],
        }
        const preview = datastreamCommand(request, {
          outputDir,
          realization: realization as RealizationId,
        })
        if (!preview?.ready) {
          res.statusCode = 400
          res.end("The run request is incomplete.\n")
          return
        }
        if (!existsSync(SCRIPT)) {
          res.statusCode = 500
          res.end("DataStreamCLI script was not found.\n")
          return
        }
        res.statusCode = 200
        res.setHeader("content-type", "text/plain; charset=utf-8")
        res.setHeader("cache-control", "no-cache")
        const child = spawn("bash", [SCRIPT, ...preview.argv], {
          cwd: DATASTREAM_ROOT,
          env: process.env,
        })
        running = child
        const write = (chunk: Buffer) => {
          if (!res.writableEnded) res.write(chunk)
        }
        child.stdout?.on("data", write)
        child.stderr?.on("data", write)
        child.on("error", (error) => {
          if (!res.writableEnded) res.end(`\n${error.message}\n`)
          if (running === child) running = null
        })
        child.on("close", (code) => {
          if (!res.writableEnded) res.end(`\nDataStreamCLI exited ${code ?? "unknown"}.\n`)
          if (running === child) running = null
        })
        res.on("close", () => {
          if (running === child && child.exitCode === null && !child.killed) child.kill("SIGTERM")
        })
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), datastreamApi()],
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
  },
})
