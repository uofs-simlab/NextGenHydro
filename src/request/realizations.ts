export const REALIZATIONS = [
  { id: "realization_sloth_nom_cfe_pet_troute.json", label: "CFE, PET, Noah-OWP, and t-route" },
  { id: "realization_sloth_nom_cfe_pet.json", label: "CFE, PET, and Noah-OWP" },
  { id: "realization_sloth_troute.json", label: "SLOTH and t-route" },
  { id: "realization_rust_lstm_troute.json", label: "Rust LSTM and t-route" },
  { id: "realization_rust_lstm.json", label: "Rust LSTM" },
  { id: "realization_python_lstm_troute.json", label: "Python LSTM and t-route" },
] as const

export type RealizationId = (typeof REALIZATIONS)[number]["id"]

export const DEFAULT_REALIZATION: RealizationId = "realization_sloth_nom_cfe_pet_troute.json"

export type RunOptions = {
  outputDir: string
  realization: RealizationId
}

export const DEFAULT_RUN_OPTIONS: RunOptions = {
  outputDir: "",
  realization: DEFAULT_REALIZATION,
}

export function outputDirFor(gage: string, outputDir: string): string {
  const typed = outputDir.trim()
  if (typed) return typed
  return gage ? `./data/gage-${gage}` : ""
}

export function isRealizationId(value: string): value is RealizationId {
  return REALIZATIONS.some((item) => item.id === value)
}
