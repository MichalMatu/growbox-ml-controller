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
 * face sizes are extended to exactly meet or overlap at the corners
 * to ensure a perfect light seal against shadow map bias.
 */
export function buildShellPanels(
  widthM: number,
  depthM: number,
  heightM: number,
  thicknessM: number = CHAMBER_GEOMETRY.wallThicknessM,
  uvTilesPerMeter: number = CHAMBER_GEOMETRY.uvTilesPerMeter,
): readonly ShellPanelSpec[] {
  const halfW = widthM / 2
  const halfD = depthM / 2
  const t = thicknessM
  const uv = uvTilesPerMeter

  // Extend panels fully to the mathematical outer corners to completely seal
  // against light bleeding. The frame is inset and will stay safely inside.
  const faceW = Math.max(widthM, t)
  const faceD = Math.max(depthM, t)
  const faceH = Math.max(heightM, t)

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
      size: [faceW, faceH + t],
      position: [0, (heightM - t) / 2, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [faceW * uv, (faceH + t) * uv],
    },
    // left (-X)
    {
      size: [faceD, faceH + t],
      position: [-halfW + t / 2, (heightM - t) / 2, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [faceD * uv, (faceH + t) * uv],
    },
    // right (+X)
    {
      size: [faceD, faceH + t],
      position: [halfW - t / 2, (heightM - t) / 2, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [faceD * uv, (faceH + t) * uv],
    },
  ]
}
