import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"

/**
 * Grow-light catalog for the chamber playground (not v4 ML features).
 * Bounding boxes are conservative class sizes for fit checks inside the tent.
 * Forms: LED panel/bar, HPS box hood, HPS wing, HPS air-cooled tube.
 */

export type LightForm = "none" | "led_panel" | "hps_box" | "hps_wing" | "hps_cooltube"

export type LightPresetId =
  | "none"
  | "led_board_60"
  | "led_board_90"
  | "led_bar_100"
  | "hps_box_600"
  | "hps_box_1000"
  | "hps_wing_600"
  | "hps_tube_600"
  | "hps_tube_1000"

/** Yaw about vertical: 0 = length along tent width (X), 90 = length along depth (Z). */
export type LightOrientationDeg = 0 | 90

export type LightPreset = {
  readonly id: LightPresetId
  readonly form: LightForm
  /** UI label (Polish product copy OK). */
  readonly label: string
  /** Fixture length along primary axis (cm) — body AABB. */
  readonly lengthCm: number
  /** Fixture width perpendicular to length (cm). */
  readonly widthCm: number
  /** Vertical body height (cm). */
  readonly heightCm: number
  /** Nominal power for label only. */
  readonly powerW: number
  /** Cooltube duct outer diameter (cm), if any. */
  readonly ductDiameterCm?: number
  /** Short note on dimension class. */
  readonly sourceNote: string
}

export const LIGHT_PRESETS: readonly LightPreset[] = [
  {
    id: "none",
    form: "none",
    label: "Brak",
    lengthCm: 0,
    widthCm: 0,
    heightCm: 0,
    powerW: 0,
    sourceNote: "no fixture",
  },
  {
    id: "led_board_60",
    form: "led_panel",
    label: "LED panel ~60×60",
    lengthCm: 60,
    widthCm: 60,
    heightCm: 8,
    powerW: 200,
    sourceNote: "class ~SF2000 / MH TS 1000 footprint",
  },
  {
    id: "led_board_90",
    form: "led_panel",
    label: "LED panel ~90×80",
    lengthCm: 90,
    widthCm: 80,
    heightCm: 9,
    powerW: 450,
    sourceNote: "class ~SF4000 footprint",
  },
  {
    id: "led_bar_100",
    form: "led_panel",
    label: "LED bar ~100 cm",
    lengthCm: 100,
    widthCm: 12,
    heightCm: 6,
    powerW: 120,
    sourceNote: "single bar class ~100 cm",
  },
  {
    id: "hps_box_600",
    form: "hps_box",
    label: "HPS 600 W skrzynka",
    lengthCm: 50,
    widthCm: 40,
    heightCm: 22,
    powerW: 600,
    sourceNote: "box / hood reflector class 600 W",
  },
  {
    id: "hps_box_1000",
    form: "hps_box",
    label: "HPS 1000 W skrzynka",
    lengthCm: 55,
    widthCm: 45,
    heightCm: 25,
    powerW: 1000,
    sourceNote: "box / hood reflector class 1000 W",
  },
  {
    id: "hps_wing_600",
    form: "hps_wing",
    label: "HPS 600 W skrzydło",
    lengthCm: 55,
    widthCm: 50,
    heightCm: 12,
    powerW: 600,
    sourceNote: "adjustable wing reflector class 600 W",
  },
  {
    id: "hps_tube_600",
    form: "hps_cooltube",
    label: "HPS 600 W cooltube Ø125",
    lengthCm: 55,
    widthCm: 18,
    heightCm: 18,
    powerW: 600,
    ductDiameterCm: 12.5,
    sourceNote: "air-cooled tube Ø125 mm class 600 W",
  },
  {
    id: "hps_tube_1000",
    form: "hps_cooltube",
    label: "HPS 1000 W cooltube Ø150",
    lengthCm: 60,
    widthCm: 20,
    heightCm: 20,
    powerW: 1000,
    ductDiameterCm: 15,
    sourceNote: "air-cooled tube Ø150 mm class 1000 W",
  },
] as const

export const DEFAULT_LIGHT_PRESET_ID: LightPresetId = "led_board_60"
export const DEFAULT_LIGHT_ORIENTATION_DEG: LightOrientationDeg = 0
/** Default gap from inner roof fabric to top of fixture (cm). */
export const DEFAULT_LIGHT_CEILING_GAP_CM = 5
/** Hard floor for ceiling gap control (cm). */
export const LIGHT_CEILING_GAP_MIN_CM = 2
/** Keep fixture bottom at least this far above floor (cm). */
export const LIGHT_FLOOR_CLEARANCE_MIN_CM = 40
/** Side margin from walls/frame so body is not jammed (m). */
export const LIGHT_WALL_MARGIN_M = 0.03

export type OrientedFootprintCm = {
  readonly extentXCm: number
  readonly extentZCm: number
}

export type LightPlacementM = {
  readonly x: number
  readonly y: number
  readonly z: number
  readonly rotationYRad: number
  readonly extentXM: number
  readonly extentZM: number
  readonly heightM: number
}

export type LightFitResult = {
  readonly fits: boolean
  readonly fitsHorizontal: boolean
  readonly fitsVertical: boolean
  readonly usableWidthCm: number
  readonly usableDepthCm: number
  readonly usableHeightCm: number
  readonly ceilingGapCm: number
  readonly maxCeilingGapCm: number
  readonly placement: LightPlacementM | null
}

export function getLightPreset(id: LightPresetId): LightPreset {
  const found = LIGHT_PRESETS.find((entry) => entry.id === id)
  if (!found) {
    return LIGHT_PRESETS.find((entry) => entry.id === DEFAULT_LIGHT_PRESET_ID)!
  }
  return found
}

export function isLightOrientationDeg(value: number): value is LightOrientationDeg {
  return value === 0 || value === 90
}

export function clampLightOrientationDeg(value: number): LightOrientationDeg {
  return value === 90 ? 90 : 0
}

/**
 * AABB on the floor plane after yaw (0°: length → X, 90°: length → Z).
 */
export function orientedFootprintCm(
  preset: LightPreset,
  orientationDeg: LightOrientationDeg,
): OrientedFootprintCm {
  if (preset.form === "none") {
    return { extentXCm: 0, extentZCm: 0 }
  }
  if (orientationDeg === 90) {
    return { extentXCm: preset.widthCm, extentZCm: preset.lengthCm }
  }
  return { extentXCm: preset.lengthCm, extentZCm: preset.widthCm }
}

/** Inner clear span after wall + frame + light margin (meters). */
export function usableLightVolumeM(
  widthM: number,
  depthM: number,
  heightM: number,
): { widthM: number; depthM: number; heightM: number } {
  const sideInset =
    CHAMBER_GEOMETRY.wallThicknessM +
    CHAMBER_GEOMETRY.frameRadiusM * 2 +
    LIGHT_WALL_MARGIN_M
  const verticalInset =
    CHAMBER_GEOMETRY.wallThicknessM + CHAMBER_GEOMETRY.frameRadiusM * 2
  return {
    widthM: Math.max(0, widthM - 2 * sideInset),
    depthM: Math.max(0, depthM - 2 * sideInset),
    heightM: Math.max(0, heightM - 2 * verticalInset),
  }
}

/**
 * Max ceiling gap so the fixture still clears the floor minimum.
 * bodyHeight + minFloorClearance + gap <= usable height.
 */
export function maxCeilingGapCm(
  tentHeightM: number,
  bodyHeightCm: number,
): number {
  if (bodyHeightCm <= 0) return LIGHT_CEILING_GAP_MIN_CM
  const usable = usableLightVolumeM(1, 1, tentHeightM).heightM * 100
  const maxGap = Math.floor(
    usable - bodyHeightCm - LIGHT_FLOOR_CLEARANCE_MIN_CM,
  )
  return Math.max(LIGHT_CEILING_GAP_MIN_CM, maxGap)
}

export function clampCeilingGapCm(
  gapCm: number,
  tentHeightM: number,
  bodyHeightCm: number,
): number {
  if (!Number.isFinite(gapCm)) return DEFAULT_LIGHT_CEILING_GAP_CM
  const maxGap = maxCeilingGapCm(tentHeightM, bodyHeightCm)
  const rounded = Math.round(gapCm)
  if (rounded < LIGHT_CEILING_GAP_MIN_CM) return LIGHT_CEILING_GAP_MIN_CM
  if (rounded > maxGap) return maxGap
  return rounded
}

/**
 * Place fixture under the roof, centered in XY.
 * `ceilingGapCm` is from inner roof plane down to the top of the AABB.
 */
export function placeLightM(
  _widthM: number,
  _depthM: number,
  heightM: number,
  preset: LightPreset,
  orientationDeg: LightOrientationDeg,
  ceilingGapCm: number,
): LightPlacementM | null {
  if (preset.form === "none") return null
  void _widthM
  void _depthM

  const bodyHeightM = preset.heightCm / 100
  const gapM = clampCeilingGapCm(ceilingGapCm, heightM, preset.heightCm) / 100
  const verticalInset =
    CHAMBER_GEOMETRY.wallThicknessM + CHAMBER_GEOMETRY.frameRadiusM * 2
  const topY = heightM - verticalInset - gapM
  const centerY = topY - bodyHeightM / 2
  const footprint = orientedFootprintCm(preset, orientationDeg)

  return {
    x: 0,
    y: centerY,
    z: 0,
    rotationYRad: (orientationDeg * Math.PI) / 180,
    extentXM: footprint.extentXCm / 100,
    extentZM: footprint.extentZCm / 100,
    heightM: bodyHeightM,
  }
}

export function planLightFit(
  widthM: number,
  depthM: number,
  heightM: number,
  preset: LightPreset,
  orientationDeg: LightOrientationDeg,
  ceilingGapCm: number,
): LightFitResult {
  const volume = usableLightVolumeM(widthM, depthM, heightM)
  const usableWidthCm = volume.widthM * 100
  const usableDepthCm = volume.depthM * 100
  const usableHeightCm = volume.heightM * 100

  if (preset.form === "none") {
    return {
      fits: true,
      fitsHorizontal: true,
      fitsVertical: true,
      usableWidthCm,
      usableDepthCm,
      usableHeightCm,
      ceilingGapCm: LIGHT_CEILING_GAP_MIN_CM,
      maxCeilingGapCm: LIGHT_CEILING_GAP_MIN_CM,
      placement: null,
    }
  }

  const gap = clampCeilingGapCm(ceilingGapCm, heightM, preset.heightCm)
  const maxGap = maxCeilingGapCm(heightM, preset.heightCm)
  const footprint = orientedFootprintCm(preset, orientationDeg)
  const fitsHorizontal =
    footprint.extentXCm <= usableWidthCm + 1e-6 &&
    footprint.extentZCm <= usableDepthCm + 1e-6
  const fitsVertical =
    preset.heightCm + LIGHT_FLOOR_CLEARANCE_MIN_CM + gap <= usableHeightCm + 1e-6 &&
    maxGap >= LIGHT_CEILING_GAP_MIN_CM

  const fits = fitsHorizontal && fitsVertical
  const placement = fits
    ? placeLightM(widthM, depthM, heightM, preset, orientationDeg, gap)
    : null

  return {
    fits,
    fitsHorizontal,
    fitsVertical,
    usableWidthCm,
    usableDepthCm,
    usableHeightCm,
    ceilingGapCm: gap,
    maxCeilingGapCm: maxGap,
    placement,
  }
}
