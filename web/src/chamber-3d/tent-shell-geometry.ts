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
 * dual-plane fabric (±thickness/2) is applied by the renderer.
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

  return [
    // floor
    {
      size: [widthM, depthM],
      position: [0, t / 2, 0],
      rotation: [Math.PI / 2, 0, 0],
      uvScale: [widthM * uv, depthM * uv],
    },
    // ceiling
    {
      size: [widthM, depthM],
      position: [0, heightM - t / 2, 0],
      rotation: [-Math.PI / 2, 0, 0],
      uvScale: [widthM * uv, depthM * uv],
    },
    // back (-Z)
    {
      size: [widthM, heightM],
      position: [0, heightM / 2, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [widthM * uv, heightM * uv],
    },
    // left (-X)
    {
      size: [depthM, heightM],
      position: [-halfW + t / 2, heightM / 2, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [depthM * uv, heightM * uv],
    },
    // right (+X)
    {
      size: [depthM, heightM],
      position: [halfW - t / 2, heightM / 2, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [depthM * uv, heightM * uv],
    },
  ]
}
