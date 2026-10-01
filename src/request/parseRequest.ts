import { FORCINGS, type ForcingId } from "./forcings.ts"

export type ParsedRequest = {
  gage: string
  start: string
  end: string
  forcing: ForcingId | ""
}

const MONTHS: Record<string, number> = {
  january: 1,
  jan: 1,
  february: 2,
  feb: 2,
  march: 3,
  mar: 3,
  april: 4,
  apr: 4,
  may: 5,
  june: 6,
  jun: 6,
  july: 7,
  jul: 7,
  august: 8,
  aug: 8,
  september: 9,
  sept: 9,
  sep: 9,
  october: 10,
  oct: 10,
  november: 11,
  nov: 11,
  december: 12,
  dec: 12,
}

const MONTH_PATTERN = Object.keys(MONTHS)
  .sort((a, b) => b.length - a.length)
  .join("|")

type FoundDate = {
  index: number
  length: number
  iso: string
}

function pad(value: number): string {
  return String(value).padStart(2, "0")
}

function toIso(year: number, month: number, day: number, hour: number, minute: number): string | null {
  if (year < 1970 || year > 2100) return null
  if (month < 1 || month > 12 || day < 1 || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null
  }
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null
  }
  return `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}`
}

function hourFromClock(hourText: string, meridiem: string | undefined): number | null {
  let hour = Number(hourText)
  if (!meridiem) return hour
  const marker = meridiem.toLowerCase()
  if (marker === "pm" && hour < 12) hour += 12
  if (marker === "am" && hour === 12) hour = 0
  if (hour > 23) return null
  return hour
}

function pushDate(found: FoundDate[], index: number, length: number, iso: string | null) {
  if (!iso) return
  const overlaps = found.some((item) => index < item.index + item.length && index + length > item.index)
  if (overlaps) return
  found.push({ index, length, iso })
}

function applyClock(text: string, found: FoundDate) {
  const after = text.slice(found.index + found.length, found.index + found.length + 24)
  const clock = after.match(/^\s*(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i)
  if (!clock) return
  const hour = hourFromClock(clock[1], clock[3])
  if (hour === null) return
  const minute = clock[2] ? Number(clock[2]) : 0
  const parts = found.iso.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!parts) return
  const iso = toIso(Number(parts[1]), Number(parts[2]), Number(parts[3]), hour, minute)
  if (!iso) return
  found.iso = iso
  found.length += clock[0].length
}

function findDates(text: string): FoundDate[] {
  const found: FoundDate[] = []
  const compact = /\b(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\b/g
  for (const match of text.matchAll(compact)) {
    pushDate(
      found,
      match.index ?? 0,
      match[0].length,
      toIso(Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4]), Number(match[5])),
    )
  }
  const iso = /\b(20\d{2})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?\b/g
  for (const match of text.matchAll(iso)) {
    pushDate(
      found,
      match.index ?? 0,
      match[0].length,
      toIso(Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4] ?? 0), Number(match[5] ?? 0)),
    )
  }
  const dayFirst = new RegExp(`\\b(\\d{1,2})\\s+(${MONTH_PATTERN})\\s+(20\\d{2})\\b`, "gi")
  for (const match of text.matchAll(dayFirst)) {
    const month = MONTHS[match[2].toLowerCase()]
    pushDate(found, match.index ?? 0, match[0].length, toIso(Number(match[3]), month, Number(match[1]), 0, 0))
  }
  const monthFirst = new RegExp(`\\b(${MONTH_PATTERN})\\s+(\\d{1,2}),?\\s+(20\\d{2})\\b`, "gi")
  for (const match of text.matchAll(monthFirst)) {
    const month = MONTHS[match[1].toLowerCase()]
    pushDate(found, match.index ?? 0, match[0].length, toIso(Number(match[3]), month, Number(match[2]), 0, 0))
  }
  found.sort((a, b) => a.index - b.index)
  for (const date of found) applyClock(text, date)
  return found
}

function roleFor(text: string, date: FoundDate): "start" | "end" | "" {
  const before = text.slice(Math.max(0, date.index - 28), date.index).toLowerCase()
  if (/\b(?:from|starting|start)\b/.test(before)) return "start"
  if (/\b(?:through|until|to)\b/.test(before)) return "end"
  return ""
}

function maskDates(text: string, dates: FoundDate[]): string {
  const chars = text.split("")
  for (const date of dates) {
    for (let index = date.index; index < date.index + date.length && index < chars.length; index += 1) {
      chars[index] = " "
    }
  }
  return chars.join("")
}

function readGage(text: string, dates: FoundDate[]): string {
  const masked = maskDates(text, dates)
  const labeled = masked.match(/\b(?:usgs|gage|gauge|site)\s*#?\s*(\d{7,15})\b/i)
  if (labeled) return labeled[1]
  const bare = masked.match(/\b(\d{7,15})\b/)
  return bare?.[1] ?? ""
}

function addDuration(iso: string, amount: number, unit: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)
  if (!match) return iso
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5])))
  const name = unit.toLowerCase()
  if (name.startsWith("hour") || name === "hr") date.setUTCHours(date.getUTCHours() + amount)
  else if (name.startsWith("week")) date.setUTCDate(date.getUTCDate() + amount * 7)
  else date.setUTCDate(date.getUTCDate() + amount)
  return toIso(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes()) ?? iso
}

function readForcing(text: string): ForcingId | "" {
  for (const item of FORCINGS) {
    if (new RegExp(`\\b${item.id}\\b`, "i").test(text)) return item.id
  }
  const value = text.toLowerCase()
  if (/\b(?:retrospective|retro)\s+v(?:ersion\s*)?2\b/.test(value) || /\bv2\s+retrospective\b/.test(value)) {
    return "NWM_RETRO_V2"
  }
  if (/\b(?:retrospective|retro)\s+v(?:ersion\s*)?3\b/.test(value)) return "NWM_RETRO_V3"
  if (/\bshort[\s-]*range\b/.test(value)) return "NWM_V3_SHORT_RANGE"
  if (/\bmedium[\s-]*range\b/.test(value)) return "NWM_V3_MEDIUM_RANGE"
  if (/\banalysis(?:\s+and|\s*&\s*|\s+)assimilation\b/.test(value)) return "NWM_V3_ANALYSIS_ASSIM"
  if (/\b(?:retrospective|retro)\b/.test(value)) return "NWM_RETRO_V3"
  if (/\bnomads\b/.test(value)) return "NOMADS_OPERATIONAL"
  if (/\boperational\b/.test(value)) return "NWM_OPERATIONAL_V3"
  return ""
}

export function parseRequest(text: string): ParsedRequest {
  const dates = findDates(text)
  let start = ""
  let end = ""
  const unassigned: FoundDate[] = []
  for (const date of dates) {
    const role = roleFor(text, date)
    if (role === "start" && !start) start = date.iso
    else if (role === "end" && !end) end = date.iso
    else unassigned.push(date)
  }
  if (!start && unassigned.length > 0) start = unassigned.shift()?.iso ?? ""
  if (!end && unassigned.length > 0) end = unassigned.shift()?.iso ?? ""
  const duration = text.match(/\b(\d+)\s*-?\s*(hour|hr|day|week)s?\b/i)
  if (duration && start) {
    end = addDuration(start, Number(duration[1]), duration[2])
  }

  return {
    gage: readGage(text, dates),
    start,
    end,
    forcing: readForcing(text),
  }
}

export function toDatastreamTime(iso: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)
  if (!match) return ""
  return `${match[1]}${match[2]}${match[3]}${match[4]}${match[5]}`
}

export function mergeRequest(current: ParsedRequest, parsed: ParsedRequest): ParsedRequest {
  return {
    gage: parsed.gage || current.gage,
    start: parsed.start || current.start,
    end: parsed.end || current.end,
    forcing: parsed.forcing,
  }
}

export const EMPTY_REQUEST: ParsedRequest = {
  gage: "",
  start: "",
  end: "",
  forcing: "",
}
