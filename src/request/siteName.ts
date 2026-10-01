export function displayStationName(raw: string): string {
  const titled = raw.toLowerCase().replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
  return titled.replace(/, ([A-Za-z]{2})$/, (_, state: string) => `, ${state.toUpperCase()}`)
}

export function stationNameFromRdb(text: string): string | null {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("#"))
  if (rows.length < 3) return null
  const headers = rows[0].split("\t")
  const nameIndex = headers.indexOf("station_nm")
  if (nameIndex < 0) return null
  const name = rows[2].split("\t")[nameIndex]?.trim()
  return name ? displayStationName(name) : null
}

export async function lookupStationName(gage: string, signal: AbortSignal): Promise<string | null> {
  const response = await fetch(
    `https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=${encodeURIComponent(gage)}&siteStatus=all`,
    { signal },
  )
  if (!response.ok) return null
  return stationNameFromRdb(await response.text())
}
