export const FORCINGS = [
  { id: "NWM_RETRO_V3", label: "National Water Model v3 retrospective" },
  { id: "NWM_RETRO_V2", label: "National Water Model v2 retrospective" },
  { id: "NWM_OPERATIONAL_V3", label: "National Water Model v3 operational" },
  { id: "NOMADS_OPERATIONAL", label: "NOMADS operational" },
  { id: "NWM_V3_SHORT_RANGE", label: "National Water Model v3 short range" },
  { id: "NWM_V3_MEDIUM_RANGE", label: "National Water Model v3 medium range" },
  { id: "NWM_V3_ANALYSIS_ASSIM", label: "National Water Model v3 analysis and assimilation" },
] as const

export type ForcingId = (typeof FORCINGS)[number]["id"]
