import { CHAMBER_GEOMETRY } from "@/chamber-3d/core/scene-tokens"

export type Vec3 = readonly [number, number, number]

export type FrameCornerBox = {
  readonly xL: number
  readonly xR: number
  readonly yBottom: number
  readonly yTop: number
  readonly zBack: number
  readonly zFront: number
}

/**
 * Axis-aligned outer-corner cage: tube centers sit `radius + eps` inside the
 * outer envelope on every face (X, Y, Z). Same inset on all axes keeps
 * uprights and rails mutually perpendicular (true 90° box).
 */
export function computeFrameCornerBox(
  widthM: number,
  depthM: number,
  heightM: number,
  radiusM: number,
  contactEpsilonM: number = CHAMBER_GEOMETRY.frameContactEpsilonM,
): FrameCornerBox {
  const inset = radiusM + contactEpsilonM
  return {
    xL: -widthM / 2 + inset,
    xR: widthM / 2 - inset,
    yBottom: inset,
    yTop: heightM - inset,
    zBack: -depthM / 2 + inset,
    zFront: depthM / 2 - inset,
  }
}

/** Eight orthotope corner points (tube centerline intersections). */
export type FrameCorners = readonly [
  Vec3,
  Vec3,
  Vec3,
  Vec3,
  Vec3,
  Vec3,
  Vec3,
  Vec3,
]

export function buildFrameCorners(box: FrameCornerBox): FrameCorners {
  const { xL, xR, yBottom, yTop, zBack, zFront } = box
  return [
    [xL, yBottom, zBack],
    [xR, yBottom, zBack],
    [xL, yBottom, zFront],
    [xR, yBottom, zFront],
    [xL, yTop, zBack],
    [xR, yTop, zBack],
    [xL, yTop, zFront],
    [xR, yTop, zFront],
  ]
}

/** Build the 12 edge segments of the rectangular frame cage. */
export function buildFrameSegments(
  box: FrameCornerBox,
): ReadonlyArray<readonly [Vec3, Vec3]> {
  const [bl, br, fl, fr, tl, tr, tfl, tfr] = buildFrameCorners(box)

  return [
    // uprights (parallel to +Y)
    [bl, tl],
    [br, tr],
    [fl, tfl],
    [fr, tfr],
    // bottom rectangle
    [bl, br],
    [br, fr],
    [fr, fl],
    [fl, bl],
    // top rectangle
    [tl, tr],
    [tr, tfr],
    [tfr, tfl],
    [tfl, tl],
  ]
}
