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

  // UWAGA: Materiały growboxu NIE MOGĄ przepuszczać światła.
  // Aby usunąć przenikanie światła z dolnej części growboxa (light leak na szwach),
  // ściany boczne muszą schodzić poniżej poziomu podłogi (bleed).
  // Jednocześnie, aby uniknąć Z-fightingu (zbugowanego przenikania tekstur na krawędziach),
  // podłoga jest schowana wewnątrz, oddzielona od ścian o 1 milimetr (eps).

  const bleed = 0.02
  const eps = 0.001
  const wallH = heightM - t + bleed
  const wallY = (heightM - t - bleed) / 2

  const faceW = Math.max(widthM, t)
  const faceD = Math.max(depthM, t)

  return [
    // floor - tucked inside walls with 1mm gap to prevent internal Z-fighting
    {
      size: [faceW - 2 * t - 2 * eps, faceD - t - eps],
      position: [0, t / 2, t / 2 + eps / 2],
      rotation: [Math.PI / 2, 0, 0],
      uvScale: [(faceW - 2 * t) * uv, (faceD - t) * uv],
    },
    // ceiling - full width/depth lid
    {
      size: [faceW, faceD],
      position: [0, heightM - t / 2, 0],
      rotation: [-Math.PI / 2, 0, 0],
      uvScale: [faceW * uv, faceD * uv],
    },
    // back (-Z) - tucked between left/right, extends below 0
    {
      size: [faceW - 2 * t, wallH],
      position: [0, wallY, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [(faceW - 2 * t) * uv, wallH * uv],
    },
    // left (-X) - extends below 0
    {
      size: [faceD, wallH],
      position: [-halfW + t / 2, wallY, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [faceD * uv, wallH * uv],
    },
    // right (+X) - extends below 0
    {
      size: [faceD, wallH],
      position: [halfW - t / 2, wallY, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [faceD * uv, wallH * uv],
    },
  ]
}
