import { CHAMBER_GEOMETRY } from "@/chamber-3d/core/scene-tokens"

/**
 * Minimum ceiling gap the lamp must use so its top sits at least
 * FAN_LIGHT_MIN_GAP_M (2 cm) below the fan body.
 * Returns null when no fan is active.
 *
 * Formula: gap = tentHeight - verticalInset - (fanBottomY - minGap)
 * where fanBottomY = fanY - fanHeightM / 2
 */
export function computeLightCeilingGapForFan(
  tentHeightM: number,
  fanPlacement: FanPlacementM | null,
  _lightBodyHeightCm: number,
): number | null {
  if (fanPlacement == null) return null
  void _lightBodyHeightCm
  const fanBottomY = fanPlacement.y - fanPlacement.heightM / 2
  const verticalInset =
    CHAMBER_GEOMETRY.wallThicknessM + CHAMBER_GEOMETRY.frameRadiusM * 2
  const maxLightTopY = fanBottomY - FAN_LIGHT_MIN_GAP_M
  const minGapM = tentHeightM - verticalInset - maxLightTopY
  const minGapCm = Math.round(minGapM * 100)
  return Math.max(FAN_CEILING_GAP_MIN_CM, minGapCm)
}

/**
 * Inline duct fan catalog for the chamber playground.
 * Real-world sizes based on Vents TT / Prima Klima / RVK / Can-Fan class devices.
 * Shape: central cylinder (motor body) → two cones (reducers) → two cylindrical spigots.
 */

export type FanForm = "none" | "inline_duct"

export type FanPresetId =
  | "none"
  | "fan_100"
  | "fan_125"
  | "fan_150"
  | "fan_200"

/** Yaw about vertical: 0 = length along tent width (X), 90 = length along depth (Z). */
export type FanOrientationDeg = 0 | 90

export type FanPreset = {
  readonly id: FanPresetId
  readonly form: FanForm
  /** UI label. */
  readonly label: string
  /** Nominal duct diameter (cm) — spigot outer diameter. */
  readonly ductDiameterCm: number
  /** Motor body diameter (cm) — widest part. */
  readonly bodyDiameterCm: number
  /** Total length from spigot tip to spigot tip (cm). */
  readonly totalLengthCm: number
  /** Central motor body length (cm). */
  readonly bodyLengthCm: number
  /** Single reducer cone length (cm). */
  readonly coneLengthCm: number
  /** Single spigot cylinder length (cm). */
  readonly ductLengthCm: number
  /** Nominal power for label only. */
  readonly powerW: number
  /** Short note on dimension class. */
  readonly sourceNote: string
}

export const FAN_PRESETS: readonly FanPreset[] = [
  {
    id: "none",
    form: "none",
    label: "Brak",
    ductDiameterCm: 0,
    bodyDiameterCm: 0,
    totalLengthCm: 0,
    bodyLengthCm: 0,
    coneLengthCm: 0,
    ductLengthCm: 0,
    powerW: 0,
    sourceNote: "no fan",
  },
  {
    id: "fan_100",
    form: "inline_duct",
    label: "Wentylator Ø100 mm",
    ductDiameterCm: 10.0,
    bodyDiameterCm: 12.5,
    totalLengthCm: 26,
    bodyLengthCm: 14,
    coneLengthCm: 2,
    ductLengthCm: 4,
    powerW: 30,
    sourceNote: "class Vents TT 100 / Prima Klima 100 mm",
  },
  {
    id: "fan_125",
    form: "inline_duct",
    label: "Wentylator Ø125 mm",
    ductDiameterCm: 12.5,
    bodyDiameterCm: 14.5,
    totalLengthCm: 28,
    bodyLengthCm: 15,
    coneLengthCm: 2.5,
    ductLengthCm: 4,
    powerW: 45,
    sourceNote: "class Vents TT 125 / RVK 125 mm",
  },
  {
    id: "fan_150",
    form: "inline_duct",
    label: "Wentylator Ø150 mm",
    ductDiameterCm: 15.0,
    bodyDiameterCm: 17.5,
    totalLengthCm: 30,
    bodyLengthCm: 16,
    coneLengthCm: 3,
    ductLengthCm: 4,
    powerW: 65,
    sourceNote: "class Vents TT 150 / Can-Fan 150 mm",
  },
  {
    id: "fan_200",
    form: "inline_duct",
    label: "Wentylator Ø200 mm",
    ductDiameterCm: 20.0,
    bodyDiameterCm: 23.0,
    totalLengthCm: 33,
    bodyLengthCm: 18,
    coneLengthCm: 3.5,
    ductLengthCm: 4,
    powerW: 100,
    sourceNote: "class Vents TT 200 / Prima Klima 200 mm",
  },
] as const

export const DEFAULT_FAN_PRESET_ID: FanPresetId = "none"
export const DEFAULT_FAN_ORIENTATION_DEG: FanOrientationDeg = 0
/** Default gap from inner roof plane to top of fan body (cm). */
export const DEFAULT_FAN_CEILING_GAP_CM = 2
/** Hard floor for ceiling gap control (cm). */
export const FAN_CEILING_GAP_MIN_CM = 2
/** Keep fan bottom at least this far above floor (cm). */
export const FAN_FLOOR_CLEARANCE_MIN_CM = 40
/** Minimum horizontal gap between fan AABB and light AABB (meters). */
export const FAN_LIGHT_MIN_GAP_M = 0.02
/** Extra side clearance beyond fabric + pole radius (meters). */
export const FAN_WALL_MARGIN_M = 0.02

export const FAN_ORIENTATIONS_DEG: readonly FanOrientationDeg[] = [0, 90]

/** Predefined fan mounting positions – all in the rear half of the tent (realistic vent locations). */
export type FanPosition = "rear-left-wall" | "rear-right-wall"
export const FAN_POSITIONS: readonly FanPosition[] = ["rear-left-wall", "rear-right-wall"]
export const DEFAULT_FAN_POSITION: FanPosition = "rear-right-wall"

// ---- Placement / fit types ----

export type OrientedFanFootprintCm = {
  readonly extentXCm: number
  readonly extentZCm: number
}

/**
 * Light placement needed for collision detection.
 * We only need position, AABB extents, and height.
 */
export type LightAABB = {
  readonly centerX: number
  readonly centerY: number
  readonly centerZ: number
  readonly extentXM: number
  readonly extentZM: number
  readonly heightM: number
}

export type FanPlacementM = {
  readonly x: number
  readonly y: number
  readonly z: number
  readonly rotationYRad: number
  /** AABB extent along X after yaw (meters). */
  readonly extentXM: number
  /** AABB extent along Z after yaw (meters). */
  readonly extentZM: number
  /** Vertical body size — equals body diameter (meters). */
  readonly heightM: number
}

export type FanFitResult = {
  readonly fits: boolean
  readonly fitsHorizontal: boolean
  readonly fitsVertical: boolean
  readonly usableWidthCm: number
  readonly usableDepthCm: number
  readonly usableHeightCm: number
  readonly ceilingGapCm: number
  readonly maxCeilingGapCm: number
  readonly placement: FanPlacementM | null
  /** Orientations that pass horizontal+vertical fit for this tent/fan. */
  readonly fittingOrientations: readonly FanOrientationDeg[]
  /** Human-readable reason when fits is false. */
  readonly reason: string | null
}

// ---- Helpers ----

export function getFanPreset(id: FanPresetId): FanPreset {
  const found = FAN_PRESETS.find((entry) => entry.id === id)
  if (!found) {
    return FAN_PRESETS.find((entry) => entry.id === DEFAULT_FAN_PRESET_ID)!
  }
  return found
}

export function isFanOrientationDeg(value: number): value is FanOrientationDeg {
  return value === 0 || value === 90
}

export function clampFanOrientationDeg(value: number): FanOrientationDeg {
  return value === 90 ? 90 : 0
}

/**
 * AABB on the floor plane after yaw (0°: length → X, 90°: length → Z).
 * Fan width in the perpendicular direction = body diameter.
 */
export function orientedFanFootprintCm(
  preset: FanPreset,
  orientationDeg: FanOrientationDeg,
): OrientedFanFootprintCm {
  if (preset.form === "none") {
    return { extentXCm: 0, extentZCm: 0 }
  }
  // Mesh is built along +X then inner-rotated +90° (PI/2) around Y,
  // so the visual length runs along Z at 0° and along X at 90°.
  if (orientationDeg === 90) {
    return { extentXCm: preset.totalLengthCm, extentZCm: preset.bodyDiameterCm }
  }
  return { extentXCm: preset.bodyDiameterCm, extentZCm: preset.totalLengthCm }
}

/** Horizontal inset for fan: fabric thickness + pole radius + margin. */
export function fanSideInsetM(): number {
  return (
    CHAMBER_GEOMETRY.wallThicknessM +
    CHAMBER_GEOMETRY.frameRadiusM +
    FAN_WALL_MARGIN_M
  )
}

/** Inner clear span after wall/frame/fan margin (meters). */
export function usableFanVolumeM(
  widthM: number,
  depthM: number,
  heightM: number,
): { widthM: number; depthM: number; heightM: number } {
  const sideInset = fanSideInsetM()
  const verticalInset =
    CHAMBER_GEOMETRY.wallThicknessM + CHAMBER_GEOMETRY.frameRadiusM * 2
  return {
    widthM: Math.max(0, widthM - 2 * sideInset),
    depthM: Math.max(0, depthM - 2 * sideInset),
    heightM: Math.max(0, heightM - 2 * verticalInset),
  }
}

/**
 * Max ceiling gap so the fan still clears the floor minimum.
 * bodyDiameterCm + minFloorClearance + gap <= usable height.
 */
export function maxFanCeilingGapCm(
  tentHeightM: number,
  bodyDiameterCm: number,
): number {
  if (bodyDiameterCm <= 0) return FAN_CEILING_GAP_MIN_CM
  const usable = usableFanVolumeM(1, 1, tentHeightM).heightM * 100
  const maxGap = Math.floor(
    usable - bodyDiameterCm - FAN_FLOOR_CLEARANCE_MIN_CM,
  )
  return Math.max(FAN_CEILING_GAP_MIN_CM, maxGap)
}

export function clampFanCeilingGapCm(
  gapCm: number,
  tentHeightM: number,
  bodyDiameterCm: number,
): number {
  if (!Number.isFinite(gapCm)) return DEFAULT_FAN_CEILING_GAP_CM
  const maxGap = maxFanCeilingGapCm(tentHeightM, bodyDiameterCm)
  const rounded = Math.round(gapCm)
  if (rounded < FAN_CEILING_GAP_MIN_CM) return FAN_CEILING_GAP_MIN_CM
  if (rounded > maxGap) return maxGap
  return rounded
}

// ---- Collision detection with light ----

/**
 * Check if two AABBs on the XZ plane overlap, with a minimum gap.
 * Returns true if the gap between closest edges >= minGapM.
 */
function horizontalClearance(
  center1X: number,
  center1Z: number,
  extent1X: number,
  extent1Z: number,
  center2X: number,
  center2Z: number,
  extent2X: number,
  extent2Z: number,
  minGapM: number,
): boolean {
  const gapX =
    Math.abs(center1X - center2X) -
    (extent1X / 2 + extent2X / 2)
  const gapZ =
    Math.abs(center1Z - center2Z) -
    (extent1Z / 2 + extent2Z / 2)

  if (gapX < -1e-6 && gapZ < -1e-6) {
    return false
  }
  if (gapX < 0 && gapZ < minGapM - 1e-6) return false
  if (gapZ < 0 && gapX < minGapM - 1e-6) return false
  return true
}

/**
 * Try to find a non-colliding X position for the fan by shifting sideways.
 * Keeps Z at 0, searches X from center outward with 1 cm step.
 */
function findNonCollidingX(
  fanExtentX: number,
  fanExtentZ: number,
  light: LightAABB,
  usableWidthM: number,
  minGapM: number,
): number | null {
  const halfUsable = usableWidthM / 2
  const halfFan = fanExtentX / 2
  const stepM = 0.01
  const maxSteps = Math.ceil((halfUsable - halfFan) / stepM)

  const candidates: number[] = [0]
  for (let i = 1; i <= maxSteps; i++) {
    const offset = i * stepM
    if (-halfFan - offset >= -halfUsable) candidates.push(-offset)
    if (halfFan + offset <= halfUsable) candidates.push(offset)
  }

  for (const xOffset of candidates) {
    const ok = horizontalClearance(
      xOffset, 0,
      fanExtentX, fanExtentZ,
      light.centerX, light.centerZ,
      light.extentXM, light.extentZM,
      minGapM,
    )
    if (ok) return xOffset
  }

  return null
}

// ---- Vertical fit ----

function fanVerticalFits(
  usableHeightCm: number,
  bodyDiameterCm: number,
  gapCm: number,
  maxGapCm: number,
): boolean {
  if (bodyDiameterCm <= 0) return true
  return (
    bodyDiameterCm + FAN_FLOOR_CLEARANCE_MIN_CM + gapCm <= usableHeightCm + 1e-6 &&
    maxGapCm >= FAN_CEILING_GAP_MIN_CM
  )
}

// ---- Horizontal fit (tent walls only) ----

function fanHorizontalFitsInTent(
  usableWidthCm: number,
  usableDepthCm: number,
  preset: FanPreset,
  orientationDeg: FanOrientationDeg,
): boolean {
  if (preset.form === "none") return true
  const footprint = orientedFanFootprintCm(preset, orientationDeg)
  return (
    footprint.extentXCm <= usableWidthCm + 1e-6 &&
    footprint.extentZCm <= usableDepthCm + 1e-6
  )
}

/**
 * Orientations where the fan AABB fits the tent (horizontal + vertical).
 */
export function listFittingFanOrientations(
  widthM: number,
  depthM: number,
  heightM: number,
  preset: FanPreset,
  ceilingGapCm: number = DEFAULT_FAN_CEILING_GAP_CM,
): FanOrientationDeg[] {
  if (preset.form === "none") return [...FAN_ORIENTATIONS_DEG]

  const volume = usableFanVolumeM(widthM, depthM, heightM)
  const usableWidthCm = volume.widthM * 100
  const usableDepthCm = volume.depthM * 100
  const usableHeightCm = volume.heightM * 100
  const gap = clampFanCeilingGapCm(ceilingGapCm, heightM, preset.bodyDiameterCm)
  const maxGap = maxFanCeilingGapCm(heightM, preset.bodyDiameterCm)
  const vOk = fanVerticalFits(usableHeightCm, preset.bodyDiameterCm, gap, maxGap)
  if (!vOk) return []

  return FAN_ORIENTATIONS_DEG.filter((deg) =>
    fanHorizontalFitsInTent(usableWidthCm, usableDepthCm, preset, deg),
  )
}

/**
 * Compute target XZ for a predefined FanPosition within usable volume.
 */
function fanPositionTargetM(
  position: FanPosition,
  usableWidthM: number,
  usableDepthM: number,
  fanExtentXM: number,
  fanExtentZM: number,
): { x: number; z: number } {
  const halfW = usableWidthM / 2
  const halfD = usableDepthM / 2
  const halfFanX = fanExtentXM / 2
  const halfFanZ = fanExtentZM / 2
  const margin = 0.02

  // All positions place the fan flush against the rear wall (Z = -halfD)
  // and either against a side wall or near the rear-wall center line.
  const rearZ = -(halfD - halfFanZ - margin)
  switch (position) {
    case "rear-left-wall":
      return { x: -(halfW - halfFanX - margin), z: rearZ }
    case "rear-right-wall":
      return { x: halfW - halfFanX - margin, z: rearZ }
  }
}

/**
 * Compute fan placement under the roof at the requested position.
 * Horizontal collision with light is resolved by shifting sideways;
 * vertical collision is handled externally by pushing the lamp down.
 */
export function placeFanM(
  widthM: number,
  depthM: number,
  heightM: number,
  preset: FanPreset,
  orientationDeg: FanOrientationDeg,
  ceilingGapCm: number,
  lightAABB: LightAABB | null,
  fanPosition: FanPosition = "rear-right-wall",
): FanPlacementM | null {
  if (preset.form === "none") return null

  const bodyDiameterM = preset.bodyDiameterCm / 100
  const gapM = clampFanCeilingGapCm(ceilingGapCm, heightM, preset.bodyDiameterCm) / 100
  const volume = usableFanVolumeM(widthM, depthM, heightM)
  const verticalInset =
    CHAMBER_GEOMETRY.wallThicknessM + CHAMBER_GEOMETRY.frameRadiusM * 2
  const topY = heightM - verticalInset - gapM
  const centerY = topY - bodyDiameterM / 2
  const footprint = orientedFanFootprintCm(preset, orientationDeg)
  const extentXM = footprint.extentXCm / 100
  const extentZM = footprint.extentZCm / 100

  const target = fanPositionTargetM(fanPosition, volume.widthM, volume.depthM, extentXM, extentZM)
  let fanX = target.x
  let fanZ = target.z

  if (lightAABB != null && lightAABB.heightM > 0) {
    const clear = horizontalClearance(
      fanX, fanZ, extentXM, extentZM,
      lightAABB.centerX, lightAABB.centerZ,
      lightAABB.extentXM, lightAABB.extentZM,
      FAN_LIGHT_MIN_GAP_M,
    )
    if (!clear) {
      const xOffset = findNonCollidingX(
        extentXM, extentZM,
        { ...lightAABB, centerZ: lightAABB.centerZ - fanZ },
        volume.widthM,
        FAN_LIGHT_MIN_GAP_M,
      )
      if (xOffset != null) {
        fanX = xOffset
      } else {
        const zOffset = findNonCollidingX(
          extentZM, extentXM,
          {
            centerX: lightAABB.centerZ - fanZ,
            centerY: lightAABB.centerY,
            centerZ: lightAABB.centerX,
            extentXM: lightAABB.extentZM,
            extentZM: lightAABB.extentXM,
            heightM: lightAABB.heightM,
          },
          volume.depthM,
          FAN_LIGHT_MIN_GAP_M,
        )
        if (zOffset != null) fanZ = zOffset
      }
    }
  }

  return {
    x: fanX,
    y: centerY,
    z: fanZ,
    rotationYRad: (orientationDeg * Math.PI) / 180,
    extentXM,
    extentZM,
    heightM: bodyDiameterM,
  }
}

/**
 * Full fit check for a fan in the tent, considering light collision.
 * Fan always renders when it fits the tent bounds.
 */
export function planFanFit(
  widthM: number,
  depthM: number,
  heightM: number,
  preset: FanPreset,
  orientationDeg: FanOrientationDeg,
  ceilingGapCm: number,
  lightAABB: LightAABB | null,
  fanPosition: FanPosition = "rear-right-wall",
): FanFitResult {
  const volume = usableFanVolumeM(widthM, depthM, heightM)
  const usableWidthCm = volume.widthM * 100
  const usableDepthCm = volume.depthM * 100
  const usableHeightCm = volume.heightM * 100

  const fittingOrientations = listFittingFanOrientations(
    widthM, depthM, heightM, preset, ceilingGapCm,
  )

  if (preset.form === "none") {
    return {
      fits: true,
      fitsHorizontal: true,
      fitsVertical: true,
      usableWidthCm,
      usableDepthCm,
      usableHeightCm,
      ceilingGapCm: FAN_CEILING_GAP_MIN_CM,
      maxCeilingGapCm: FAN_CEILING_GAP_MIN_CM,
      placement: null,
      fittingOrientations,
      reason: null,
    }
  }

  const gap = clampFanCeilingGapCm(ceilingGapCm, heightM, preset.bodyDiameterCm)
  const maxGap = maxFanCeilingGapCm(heightM, preset.bodyDiameterCm)
  const fitsHorizontal = fanHorizontalFitsInTent(usableWidthCm, usableDepthCm, preset, orientationDeg)
  const fitsVertical = fanVerticalFits(usableHeightCm, preset.bodyDiameterCm, gap, maxGap)

  if (!fitsHorizontal) {
    return {
      fits: false,
      fitsHorizontal: false,
      fitsVertical,
      usableWidthCm, usableDepthCm, usableHeightCm,
      ceilingGapCm: gap,
      maxCeilingGapCm: maxGap,
      placement: null,
      fittingOrientations,
      reason: "Wentylator nie mieści się poziomo w namiocie",
    }
  }

  if (!fitsVertical) {
    return {
      fits: false,
      fitsHorizontal: true,
      fitsVertical: false,
      usableWidthCm, usableDepthCm, usableHeightCm,
      ceilingGapCm: gap,
      maxCeilingGapCm: maxGap,
      placement: null,
      fittingOrientations,
      reason: "Wentylator nie mieści się pionowo (za nisko sufitu lub za mało miejsca nad podłogą)",
    }
  }

  const placement = placeFanM(widthM, depthM, heightM, preset, orientationDeg, gap, lightAABB, fanPosition)

  return {
    fits: true,
    fitsHorizontal: true,
    fitsVertical: true,
    usableWidthCm, usableDepthCm, usableHeightCm,
    ceilingGapCm: gap,
    maxCeilingGapCm: maxGap,
    placement: placement!,
    fittingOrientations,
    reason: null,
  }
}
