import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"

/**
 * Felt / fabric grow-bag sizes for the chamber playground.
 *
 * Proportions follow common commercial fabric pots (Bootstrap Farmer style
 * charts: diameter × height), converted to cm and tagged by approximate liters
 * so they line up with schema `cultivation.pot_volume_l` (golden uses 12 L).
 *
 * Typical ratio for mid-size bags: diameter ≈ height (0.85–1.15).
 * Smaller bags trend slightly taller; larger bags slightly wider.
 */
export type FeltPotPresetId =
  | "7l"
  | "11l"
  | "12l"
  | "15l"
  | "19l"
  | "26l"
  | "38l"

export type FeltPotPreset = {
  readonly id: FeltPotPresetId
  /** Nominal soil volume (liters). */
  readonly volumeL: number
  /** Outer diameter when filled (cm). */
  readonly diameterCm: number
  /** Wall height when filled (cm). */
  readonly heightCm: number
  /** Short UI label. */
  readonly label: string
}

/**
 * Catalog of felt pots used in the 3D playground.
 * Diameters/heights are approximate manufacturer chart values (inches → cm).
 */
export const FELT_POT_PRESETS: readonly FeltPotPreset[] = [
  // ~2 gal: 8" × 7"
  { id: "7l", volumeL: 7, diameterCm: 20, heightCm: 18, label: "7 L (~2 gal)" },
  // common EU growbox 11 L
  { id: "11l", volumeL: 11, diameterCm: 25, heightCm: 23, label: "11 L" },
  // golden example pot_volume_l = 12
  { id: "12l", volumeL: 12, diameterCm: 26, heightCm: 24, label: "12 L (domyślna)" },
  { id: "15l", volumeL: 15, diameterCm: 28, heightCm: 26, label: "15 L" },
  // ~5 gal: 10" × 12"
  { id: "19l", volumeL: 19, diameterCm: 25, heightCm: 30, label: "19 L (~5 gal)" },
  // ~7 gal: 13" × 12"
  { id: "26l", volumeL: 26, diameterCm: 33, heightCm: 30, label: "26 L (~7 gal)" },
  // ~10 gal: 14.5" × 14"
  { id: "38l", volumeL: 38, diameterCm: 37, heightCm: 36, label: "38 L (~10 gal)" },
] as const

export const DEFAULT_FELT_POT_PRESET_ID: FeltPotPresetId = "12l"

/** Contract / product: at most four pot slots. */
export const FELT_POT_COUNT_MAX = 4
export const FELT_POT_COUNT_MIN = 0

export type FeltPotCount = 0 | 1 | 2 | 3 | 4

export type PotFootprintCm = {
  readonly diameterCm: number
  readonly heightCm: number
}

export type PotPositionM = {
  /** Center X in scene meters (enclosure origin at floor center). */
  readonly x: number
  /** Center Z in scene meters. */
  readonly z: number
}

export type PotLayoutPlan = {
  /** Requested count after clamp to 0–4. */
  readonly requestedCount: FeltPotCount
  /** How many pots actually fit on the floor. */
  readonly fittedCount: FeltPotCount
  /** True when every requested pot has a placement. */
  readonly fits: boolean
  /** Max pots of this size that fit (0–4). */
  readonly maxFit: FeltPotCount
  /** Centers for the pots that fit (length === fittedCount). */
  readonly positions: readonly PotPositionM[]
  /** Usable inner floor (cm) after wall/frame/margin inset. */
  readonly usableWidthCm: number
  readonly usableDepthCm: number
}

/**
 * Clearance from tent wall fabric / poles so pots are not jammed in corners.
 * ~4 cm handling margin + half of frame footprint is applied via geometry inset.
 */
export const FELT_POT_WALL_MARGIN_M = 0.04

/** Air gap between neighboring pot rims (meters). */
export const FELT_POT_GAP_M = 0.04

/** Minimum headroom above pot rim inside the tent (meters). */
export const FELT_POT_HEADROOM_M = 0.05

export function getFeltPotPreset(id: FeltPotPresetId): FeltPotPreset {
  const preset = FELT_POT_PRESETS.find((entry) => entry.id === id)
  if (!preset) {
    return FELT_POT_PRESETS.find((entry) => entry.id === DEFAULT_FELT_POT_PRESET_ID)!
  }
  return preset
}

export function clampFeltPotCount(value: number): FeltPotCount {
  if (!Number.isFinite(value)) return 0
  const rounded = Math.round(value)
  if (rounded <= 0) return 0
  if (rounded >= FELT_POT_COUNT_MAX) return FELT_POT_COUNT_MAX
  return rounded as FeltPotCount
}

/**
 * Inner floor rectangle available for pot centers' bounding boxes
 * (full diameter must stay inside this rect).
 */
export function usableFloorM(
  widthM: number,
  depthM: number,
): { widthM: number; depthM: number } {
  const inset =
    CHAMBER_GEOMETRY.wallThicknessM +
    CHAMBER_GEOMETRY.frameRadiusM * 2 +
    FELT_POT_WALL_MARGIN_M
  return {
    widthM: Math.max(0, widthM - 2 * inset),
    depthM: Math.max(0, depthM - 2 * inset),
  }
}

function cellPitchM(diameterM: number): number {
  return diameterM + FELT_POT_GAP_M
}

/**
 * How many equal cells of size `pitch` fit along `span` when each pot
 * occupies `diameter` and gaps sit only between pots.
 * span >= n * diameter + (n - 1) * gap  ⇒  span + gap >= n * pitch
 */
export function maxCellsAlong(spanM: number, diameterM: number): number {
  if (spanM < diameterM || diameterM <= 0) return 0
  const pitch = cellPitchM(diameterM)
  return Math.floor((spanM + FELT_POT_GAP_M) / pitch)
}

/**
 * Maximum number of equal circular pots (0–4) that pack on the floor.
 * Tries axis-aligned grids: 1×1, 1×2 / 2×1, 1×3 / 3×1, 2×2, 1×4 / 4×1.
 */
export function maxPotsThatFit(
  widthM: number,
  depthM: number,
  heightM: number,
  footprint: PotFootprintCm,
): FeltPotCount {
  const diameterM = footprint.diameterCm / 100
  const potHeightM = footprint.heightCm / 100
  if (potHeightM + FELT_POT_HEADROOM_M > heightM) return 0

  const floor = usableFloorM(widthM, depthM)
  const cols = maxCellsAlong(floor.widthM, diameterM)
  const rows = maxCellsAlong(floor.depthM, diameterM)
  if (cols === 0 || rows === 0) return 0

  const capacity = cols * rows
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
  count: FeltPotCount,
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
    // Reject oversized empty cells for sparse packs (e.g. 3 in 2×2 is OK).
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
      // Prefer more columns on a wide floor.
      if (b.cols !== a.cols) return b.cols - a.cols
    } else if (b.rows !== a.rows) {
      return b.rows - a.rows
    }
    return a.cols - b.cols
  })
  return candidates[0] ?? null
}

function gridPositions(
  count: FeltPotCount,
  grid: GridSpec,
  diameterM: number,
): PotPositionM[] {
  if (count === 0 || grid.cols === 0 || grid.rows === 0) return []

  const pitch = cellPitchM(diameterM)
  const blockW = grid.cols * diameterM + (grid.cols - 1) * FELT_POT_GAP_M
  const blockD = grid.rows * diameterM + (grid.rows - 1) * FELT_POT_GAP_M
  const originX = -blockW / 2 + diameterM / 2
  const originZ = -blockD / 2 + diameterM / 2

  const positions: PotPositionM[] = []
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
 * Plan pot placement inside an enclosure (meters). Centers are relative to
 * the tent floor center (same frame as the enclosure mesh).
 */
export function planFeltPotLayout(
  widthM: number,
  depthM: number,
  heightM: number,
  footprint: PotFootprintCm,
  requested: number,
): PotLayoutPlan {
  const requestedCount = clampFeltPotCount(requested)
  const floor = usableFloorM(widthM, depthM)
  const usableWidthCm = floor.widthM * 100
  const usableDepthCm = floor.depthM * 100
  const maxFit = maxPotsThatFit(widthM, depthM, heightM, footprint)
  const fittedCount = Math.min(requestedCount, maxFit) as FeltPotCount

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

  const diameterM = footprint.diameterCm / 100
  const maxCols = maxCellsAlong(floor.widthM, diameterM)
  const maxRows = maxCellsAlong(floor.depthM, diameterM)
  const grid = pickGrid(fittedCount, maxCols, maxRows, floor.widthM, floor.depthM)
  const positions = grid
    ? gridPositions(fittedCount, grid, diameterM)
    : []

  return {
    requestedCount,
    fittedCount: positions.length as FeltPotCount,
    fits: requestedCount <= maxFit && positions.length === requestedCount,
    maxFit,
    positions,
    usableWidthCm,
    usableDepthCm,
  }
}

/** Diameter-to-height ratio (diagnostic / tests). */
export function feltPotAspectRatio(preset: FeltPotPreset): number {
  return preset.diameterCm / preset.heightCm
}
