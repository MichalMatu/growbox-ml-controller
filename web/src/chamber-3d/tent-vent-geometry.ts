import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"
import type { Vec3 } from "@/chamber-3d/tent-frame-geometry"

/** One continuous zipper segment in the flap's local XY plane (Z = 0). */
export type ZipperSegment = readonly [Vec3, Vec3]

/**
 * Rectangular rear mesh-flap zipper (closed loop: all four sides).
 * No fabric cutout; track only. Always dual-sided (interior + exterior).
 */
export type RearFlapZipperSpec = {
  /** Local XY size of the rectangle (meters). */
  readonly size: readonly [number, number]
  /** Center on a back-face plane (interior or exterior). */
  readonly position: Vec3
  /** Euler XYZ for the back wall plane. */
  readonly rotation: Vec3
  /**
   * Four local segments forming a closed rectangle (CCW from top-left):
   * left upright, bottom rail, right upright, top rail.
   */
  readonly localSegments: readonly [
    ZipperSegment,
    ZipperSegment,
    ZipperSegment,
    ZipperSegment,
  ]
  /** Zipper pull tab center in local space (bottom rail midpoint). */
  readonly pullLocal: Vec3
  /** Which face of the rear wall this instance sits on. */
  readonly face: "interior" | "exterior"
}

/**
 * Build a closed rectangular zipper path in local coordinates
 * (origin = flap center; +Y = up).
 */
export function buildZipperRectSegments(
  flapWidthM: number,
  flapHeightM: number,
): readonly [ZipperSegment, ZipperSegment, ZipperSegment, ZipperSegment] {
  const hw = flapWidthM / 2
  const hh = flapHeightM / 2
  const topL: Vec3 = [-hw, hh, 0]
  const botL: Vec3 = [-hw, -hh, 0]
  const botR: Vec3 = [hw, -hh, 0]
  const topR: Vec3 = [hw, hh, 0]
  return [
    [topL, botL],
    [botL, botR],
    [botR, topR],
    [topR, topL],
  ]
}

/**
 * Rear-wall (-Z) rectangular zipper on **both** faces of the fabric
 * (interior foil + exterior nylon). Fixed 30×20 cm; empty if tent face is smaller.
 */
export function buildRearFlapZippers(
  widthM: number,
  depthM: number,
  heightM: number,
  thicknessM: number = CHAMBER_GEOMETRY.wallThicknessM,
  cornerClearanceM: number = CHAMBER_GEOMETRY.frameRadiusM,
  flapWidthM: number = CHAMBER_GEOMETRY.rearFlapWidthM,
  flapHeightM: number = CHAMBER_GEOMETRY.rearFlapHeightM,
  bottomYFromFloorM: number = CHAMBER_GEOMETRY.rearFlapBottomYFromFloorM,
  outlineOffsetM: number = CHAMBER_GEOMETRY.rearFlapOutlineOffsetM,
): readonly RearFlapZipperSpec[] {
  const halfD = depthM / 2
  const faceW = Math.max(widthM - 2 * cornerClearanceM, thicknessM)
  const faceH = Math.max(heightM - 2 * cornerClearanceM, thicknessM)

  // Fixed physical size + floor offset — must fit inside the fabric face.
  const yBottom = bottomYFromFloorM
  const yTop = yBottom + flapHeightM
  if (
    flapWidthM > faceW ||
    flapHeightM > faceH ||
    yBottom < cornerClearanceM ||
    yTop > heightM - cornerClearanceM
  ) {
    return []
  }

  const yCenter = yBottom + flapHeightM / 2

  const size = [flapWidthM, flapHeightM] as const
  const localSegments = buildZipperRectSegments(flapWidthM, flapHeightM)
  const pullLocal: Vec3 = [0, -flapHeightM / 2, 0]

  // Interior face: z = -halfD + thickness, normal into chamber (+Z).
  const zInterior = -halfD + thicknessM + outlineOffsetM
  // Exterior face: z = -halfD, normal outward (-Z) via Ry(π).
  const zExterior = -halfD - outlineOffsetM

  return [
    {
      size,
      position: [0, yCenter, zInterior],
      rotation: [0, 0, 0],
      localSegments,
      pullLocal,
      face: "interior",
    },
    {
      size,
      position: [0, yCenter, zExterior],
      // Match back exterior panel orientation (normal points -Z).
      rotation: [0, Math.PI, 0],
      localSegments,
      pullLocal,
      face: "exterior",
    },
  ]
}
