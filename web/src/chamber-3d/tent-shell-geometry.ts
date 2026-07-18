import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"
import type { Vec3 } from "@/chamber-3d/tent-frame-geometry"

export type ShellPanelSpec = {
  /** Plane width × height in local XY (meters). */
  readonly size: readonly [number, number]
  /** Panel mid-thickness center in scene space. */
  readonly position: Vec3
  /** Euler XYZ radians (R3F rotation). */
  readonly rotation: Vec3
  /** UV tile counts (U, V) for geometry baking. */
  readonly uvScale: readonly [number, number]
}

/**
 * Open-front grow-tent shell: floor, ceiling, back, left, right.
 * No front panel (+Z is the doorway). Panels sit on the outer envelope;
 * face size is reduced by `cornerClearanceM` on every edge so fabric does
 * not overhang the steel corner pockets (frame tubes + corner spheres).
 */
export function buildShellPanels(
  widthM: number,
  depthM: number,
  heightM: number,
  thicknessM: number = CHAMBER_GEOMETRY.wallThicknessM,
  uvTilesPerMeter: number = CHAMBER_GEOMETRY.uvTilesPerMeter,
  cornerClearanceM: number = CHAMBER_GEOMETRY.frameRadiusM,
): readonly ShellPanelSpec[] {
  const halfW = widthM / 2
  const halfD = depthM / 2
  const t = thicknessM
  const c = cornerClearanceM
  const uv = uvTilesPerMeter

  // Leave a frame pocket at each orthotope edge (min size = thickness).
  const faceW = Math.max(widthM - 2 * c, t)
  const faceD = Math.max(depthM - 2 * c, t)
  const faceH = Math.max(heightM - 2 * c, t)

  return [
    // floor
    {
      size: [faceW, faceD],
      position: [0, t / 2, 0],
      rotation: [Math.PI / 2, 0, 0],
      uvScale: [faceW * uv, faceD * uv],
    },
    // ceiling
    {
      size: [faceW, faceD],
      position: [0, heightM - t / 2, 0],
      rotation: [-Math.PI / 2, 0, 0],
      uvScale: [faceW * uv, faceD * uv],
    },
    // back (-Z)
    {
      size: [faceW, faceH],
      position: [0, heightM / 2, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [faceW * uv, faceH * uv],
    },
    // left (-X)
    {
      size: [faceD, faceH],
      position: [-halfW + t / 2, heightM / 2, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [faceD * uv, faceH * uv],
    },
    // right (+X)
    {
      size: [faceD, faceH],
      position: [halfW - t / 2, heightM / 2, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [faceD * uv, faceH * uv],
    },
  ]
}
