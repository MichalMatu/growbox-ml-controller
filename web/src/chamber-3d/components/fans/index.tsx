import { type FanPreset, type FanPlacementM } from "./fan-geometry"
import { type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
import { InlineFanMesh } from "./inline-fan"

export type InlineFanProps = {
  preset: FanPreset
  placement: FanPlacementM
  colors: ChamberSceneColors
}

/**
 * Parametric inline duct fan from catalog.
 * Local space: length +X, width +Z, height +Y; group applies yaw.
 */
export function InlineFan({
  preset,
  placement,
  colors,
}: InlineFanProps) {
  if (preset.form === "none") return null

  const totalLengthM = preset.totalLengthCm / 100
  const bodyDiameterM = preset.bodyDiameterCm / 100
  const bodyLengthM = preset.bodyLengthCm / 100
  const ductDiameterM = preset.ductDiameterCm / 100
  const ductLengthM = preset.ductLengthCm / 100
  const coneLengthM = preset.coneLengthCm / 100

  void totalLengthM // used for AABB fitting, not mesh

  return (
    <group
      position={[placement.x, placement.y, placement.z]}
      rotation={[0, placement.rotationYRad, 0]}
    >
      <InlineFanMesh
        bodyDiameterM={bodyDiameterM}
        bodyLengthM={bodyLengthM}
        ductDiameterM={ductDiameterM}
        ductLengthM={ductLengthM}
        coneLengthM={coneLengthM}
        colors={colors}
      />
    </group>
  )
}
