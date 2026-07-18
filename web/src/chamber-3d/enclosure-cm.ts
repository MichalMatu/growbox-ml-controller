/** UX bounds for grow-tent enclosure dimensions (cm). */
export const ENCLOSURE_CM_MIN = 40
export const ENCLOSURE_CM_MAX = 500

export function clampEnclosureCm(value: number): number {
  return Math.min(ENCLOSURE_CM_MAX, Math.max(ENCLOSURE_CM_MIN, value))
}

/**
 * Parse a draft input string. Empty / incomplete → null (keep editing).
 * Does not clamp — callers decide live preview vs blur commit.
 */
export function parseEnclosureCmDraft(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === "" || trimmed === "-" || trimmed === "+" || trimmed === ".") {
    return null
  }
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return null
  return value
}

/** True when the number is safe to drive the 3D scene while typing. */
export function isLiveEnclosureCm(value: number): boolean {
  return (
    Number.isFinite(value) &&
    value >= ENCLOSURE_CM_MIN &&
    value <= ENCLOSURE_CM_MAX
  )
}

/** Blur / Enter: round + clamp; invalid draft falls back to previous commit. */
export function commitEnclosureCm(raw: string, fallback: number): number {
  const parsed = parseEnclosureCmDraft(raw)
  if (parsed === null) return clampEnclosureCm(fallback)
  return clampEnclosureCm(Math.round(parsed))
}
