import { CHAMBER_GEOMETRY } from "@/chamber-3d/core/scene-tokens"
import type { Vec3 } from "@/chamber-3d/components/enclosure/tent-frame-geometry"

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

  // To prevent z-fighting (visible jagged edges at corners), we build
  // the walls as a perfectly butted non-overlapping box.
  // - Floor/Ceiling: full width and depth.
  // - Left/Right: sit between floor and ceiling (height - 2*t), full depth.
  // - Back: sits between all four (width - 2*t, height - 2*t).

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
    // back (-Z) - tucked between left, right, floor, ceiling
    {
      size: [faceW - 2 * t, faceH - 2 * t],
      position: [0, heightM / 2, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [(faceW - 2 * t) * uv, (faceH - 2 * t) * uv],
    },
    // left (-X) - tucked between floor and ceiling
    {
      size: [faceD, faceH - 2 * t],
      position: [-halfW + t / 2, heightM / 2, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [faceD * uv, (faceH - 2 * t) * uv],
    },
    // right (+X) - tucked between floor and ceiling
    {
      size: [faceD, faceH - 2 * t],
      position: [halfW - t / 2, heightM / 2, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [faceD * uv, (faceH - 2 * t) * uv],
    },
  ]
}
