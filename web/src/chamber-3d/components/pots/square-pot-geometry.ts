import { CHAMBER_GEOMETRY } from "@/chamber-3d/core/scene-tokens"

/**
 * Square / rectangular plastic pot sizes for the chamber playground.
 *
 * Volumes mirror the felt-pot preset catalog (7 L – 38 L) so users can
 * compare layouts at the same nominal capacity.  Height is kept identical
 * to the felt counterpart; the square side is derived as:
 *   side = round(sqrt(V_litres × 1000 / height_cm))
 *
 * Typical commercial square pots (e.g. Teku, Elho) follow similar D ≈ H
 * aspect ratios and are moulded in UV-stabilized polypropylene.
 */
export type SquarePotPresetId =
  | "7l"
  | "11l"
  | "12l"
  | "15l"
  | "19l"
  | "26l"
  | "38l"

export type SquarePotPreset = {
  readonly id: SquarePotPresetId
  /** Nominal soil volume (liters). */
  readonly volumeL: number
  /** Outer side length — width = depth (cm). */
  readonly sideCm: number
  /** Wall height when filled (cm). */
  readonly heightCm: number
  /** Short UI label. */
  readonly label: string
}

/**
 * Catalog of square pots used in the 3D playground.
 * Side lengths derived to match felt-pot volumes at identical heights.
 */
export const SQUARE_POT_PRESETS: readonly SquarePotPreset[] = [
  // 7 L felt: ⌀20 × 18  →  square 20×20 cm at same height = 7.2 L
  { id: "7l", volumeL: 7, sideCm: 20, heightCm: 18, label: "7 L (kwadrat)" },
  // 11 L felt: ⌀25 × 23  →  22×22 × 23 = 11.1 L
  { id: "11l", volumeL: 11, sideCm: 22, heightCm: 23, label: "11 L (kwadrat)" },
  // 12 L felt: ⌀26 × 24  →  22×22 × 24 = 11.6 L ≈ 12 L
  { id: "12l", volumeL: 12, sideCm: 22, heightCm: 24, label: "12 L (kwadrat, domyślna)" },
  // 15 L felt: ⌀28 × 26  →  24×24 × 26 = 15.0 L
  { id: "15l", volumeL: 15, sideCm: 24, heightCm: 26, label: "15 L (kwadrat)" },
  // 19 L felt: ⌀25 × 30  →  25×25 × 30 = 18.8 L ≈ 19 L
  { id: "19l", volumeL: 19, sideCm: 25, heightCm: 30, label: "19 L (kwadrat)" },
  // 26 L felt: ⌀33 × 30  →  29×29 × 30 = 25.2 L ≈ 26 L
  { id: "26l", volumeL: 26, sideCm: 29, heightCm: 30, label: "26 L (kwadrat)" },
  // 38 L felt: ⌀37 × 36  →  33×33 × 36 = 39.2 L ≈ 38 L
  { id: "38l", volumeL: 38, sideCm: 33, heightCm: 36, label: "38 L (kwadrat)" },
] as const

export const DEFAULT_SQUARE_POT_PRESET_ID: SquarePotPresetId = "12l"

/** Contract / product: at most nine pot slots. */
export const SQUARE_POT_COUNT_MAX = 9
export const SQUARE_POT_COUNT_MIN = 0

export type SquarePotCount = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9

export type SquarePotFootprintCm = {
  readonly sideCm: number
  readonly heightCm: number
}

export type SquarePotPositionM = {
  /** Center X in scene meters (enclosure origin at floor center). */
  readonly x: number
  /** Center Z in scene meters. */
  readonly z: number
}

export type SquarePotLayoutPlan = {
  /** Requested count after clamp to 0–9. */
  readonly requestedCount: SquarePotCount
  /** How many pots actually fit on the floor. */
  readonly fittedCount: SquarePotCount
  /** True when every requested pot has a placement. */
  readonly fits: boolean
  /** Max pots of this size that fit (0–9). */
  readonly maxFit: SquarePotCount
  /** Centers for the pots that fit (length === fittedCount). */
  readonly positions: readonly SquarePotPositionM[]
  /** Usable inner floor (cm) after wall/frame/margin inset. */
  readonly usableWidthCm: number
  readonly usableDepthCm: number
}

/**
 * Clearance from tent wall fabric / poles so pots are not jammed in corners.
 * ~4 cm handling margin + half of frame footprint is applied via geometry inset.
 */
export const SQUARE_POT_WALL_MARGIN_M = 0.04

/** Air gap between neighboring pot edges (meters). */
export const SQUARE_POT_GAP_M = 0.04

/** Minimum headroom above pot rim inside the tent (meters). */
export const SQUARE_POT_HEADROOM_M = 0.05

export function getSquarePotPreset(id: SquarePotPresetId): SquarePotPreset {
  const preset = SQUARE_POT_PRESETS.find((entry) => entry.id === id)
  if (!preset) {
    return SQUARE_POT_PRESETS.find((entry) => entry.id === DEFAULT_SQUARE_POT_PRESET_ID)!
  }
  return preset
}

export function clampSquarePotCount(value: number): SquarePotCount {
  if (!Number.isFinite(value)) return 0
  const rounded = Math.round(value)
  if (rounded <= 0) return 0
  if (rounded >= SQUARE_POT_COUNT_MAX) return SQUARE_POT_COUNT_MAX
  return rounded as SquarePotCount
}

/**
 * Inner floor rectangle available for pot centers' bounding boxes
 * (full side must stay inside this rect).
 */
export function usableFloorM(
  widthM: number,
  depthM: number,
): { widthM: number; depthM: number } {
  const inset =
    CHAMBER_GEOMETRY.wallThicknessM +
    CHAMBER_GEOMETRY.frameRadiusM * 2 +
    SQUARE_POT_WALL_MARGIN_M
  return {
    widthM: Math.max(0, widthM - 2 * inset),
    depthM: Math.max(0, depthM - 2 * inset),
  }
}

function cellPitchM(sideM: number): number {
  return sideM + SQUARE_POT_GAP_M
}

/**
 * How many equal cells of size `pitch` fit along `span` when each pot
 * occupies `side` and gaps sit only between pots.
 */
export function maxCellsAlong(spanM: number, sideM: number): number {
  if (spanM < sideM || sideM <= 0) return 0
  const pitch = cellPitchM(sideM)
  return Math.floor((spanM + SQUARE_POT_GAP_M) / pitch)
}

/**
 * Maximum number of equal square pots (0–9) that pack on the floor.
 * Tries axis-aligned grids: 1×1 through 3×3, plus 1×N / N×1 up to 9.
 */
export function maxSquarePotsThatFit(
  widthM: number,
  depthM: number,
  heightM: number,
  footprint: SquarePotFootprintCm,
): SquarePotCount {
  const sideM = footprint.sideCm / 100
  const potHeightM = footprint.heightCm / 100
  if (potHeightM + SQUARE_POT_HEADROOM_M > heightM) return 0

  const floor = usableFloorM(widthM, depthM)
  const cols = maxCellsAlong(floor.widthM, sideM)
  const rows = maxCellsAlong(floor.depthM, sideM)
  if (cols === 0 || rows === 0) return 0

  const capacity = cols * rows
  if (capacity >= 9) return 9
  if (capacity >= 8) return 8
  if (capacity >= 7) return 7
  if (capacity >= 6) return 6
  if (capacity >= 5) return 5
  if (capacity >= 4) return 4
  if (capacity >= 3) return 3
  if (capacity >= 2) return 2
  return 1
}

type GridSpec = { cols: number; rows: number }

/**
 * Prefer compact grids that fit; for a given count pick the orientation
 * that leaves more residual space (longer tent axis gets more cells).
 */
function pickGrid(
  count: SquarePotCount,
  maxCols: number,
  maxRows: number,
  usableW: number,
  usableD: number,
): GridSpec | null {
  if (count === 0) return { cols: 0, rows: 0 }

  const candidates: GridSpec[] = []
  for (let cols = 1; cols <= Math.min(count, maxCols); cols++) {
    const rows = Math.ceil(count / cols)
    if (rows > maxRows) continue
    if (cols * rows < count) continue
    candidates.push({ cols, rows })
  }
  if (candidates.length === 0) return null

  // Prefer grids closer to square on the longer floor axis.
  const preferWide = usableW >= usableD
  candidates.sort((a, b) => {
    const aWaste = a.cols * a.rows - count
    const bWaste = b.cols * b.rows - count
    if (aWaste !== bWaste) return aWaste - bWaste
    if (preferWide) {
      if (b.cols !== a.cols) return b.cols - a.cols
    } else if (b.rows !== a.rows) {
      return b.rows - a.rows
    }
    return a.cols - b.cols
  })
  return candidates[0] ?? null
}

function gridPositions(
  count: SquarePotCount,
  grid: GridSpec,
  sideM: number,
): SquarePotPositionM[] {
  if (count === 0 || grid.cols === 0 || grid.rows === 0) return []

  const pitch = cellPitchM(sideM)
  const blockW = grid.cols * sideM + (grid.cols - 1) * SQUARE_POT_GAP_M
  const blockD = grid.rows * sideM + (grid.rows - 1) * SQUARE_POT_GAP_M
  const originX = -blockW / 2 + sideM / 2
  const originZ = -blockD / 2 + sideM / 2

  const positions: SquarePotPositionM[] = []
  for (let i = 0; i < count; i++) {
    const col = i % grid.cols
    const row = Math.floor(i / grid.cols)
    positions.push({
      x: originX + col * pitch,
      z: originZ + row * pitch,
    })
  }
  return positions
}

/**
 * Plan square pot placement inside an enclosure (meters). Centers are relative to
 * the tent floor center (same frame as the enclosure mesh).
 */
export function planSquarePotLayout(
  widthM: number,
  depthM: number,
  heightM: number,
  footprint: SquarePotFootprintCm,
  requested: number,
): SquarePotLayoutPlan {
  const requestedCount = clampSquarePotCount(requested)
  const floor = usableFloorM(widthM, depthM)
  const usableWidthCm = floor.widthM * 100
  const usableDepthCm = floor.depthM * 100
  const maxFit = maxSquarePotsThatFit(widthM, depthM, heightM, footprint)
  const fittedCount = Math.min(requestedCount, maxFit) as SquarePotCount

  if (fittedCount === 0) {
    return {
      requestedCount,
      fittedCount: 0,
      fits: requestedCount === 0,
      maxFit,
      positions: [],
      usableWidthCm,
      usableDepthCm,
    }
  }

  const sideM = footprint.sideCm / 100
  const maxCols = maxCellsAlong(floor.widthM, sideM)
  const maxRows = maxCellsAlong(floor.depthM, sideM)
  const grid = pickGrid(fittedCount, maxCols, maxRows, floor.widthM, floor.depthM)
  const positions = grid
    ? gridPositions(fittedCount, grid, sideM)
    : []

  return {
    requestedCount,
    fittedCount: positions.length as SquarePotCount,
    fits: requestedCount <= maxFit && positions.length === requestedCount,
    maxFit,
    positions,
    usableWidthCm,
    usableDepthCm,
  }
}

/** Side-to-height ratio (diagnostic / tests). */
export function squarePotAspectRatio(preset: SquarePotPreset): number {
  return preset.sideCm / preset.heightCm
}
