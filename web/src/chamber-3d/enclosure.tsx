import { Edges } from "@react-three/drei"
import { DoubleSide } from "three"

import {
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

export type EnclosureDimensions = {
  widthCm: number
  depthCm: number
  heightCm: number
  colors: ChamberSceneColors
}

/**
 * Parametric grow tent shell. Schema units are cm; scene units are meters.
 * Colors come from resolveChamberSceneColors() (CSS tokens).
 */
export function Enclosure({
  widthCm,
  depthCm,
  heightCm,
  colors,
}: EnclosureDimensions) {
  const widthM = Math.max(widthCm, 1) / 100
  const depthM = Math.max(depthCm, 1) / 100
  const heightM = Math.max(heightCm, 1) / 100

  return (
    <group position={[0, heightM / 2, 0]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[widthM, heightM, depthM]} />
        <meshStandardMaterial
          color={colors.enclosureFill}
          transparent
          opacity={CHAMBER_MATERIAL.enclosureOpacity}
          side={DoubleSide}
          depthWrite={false}
        />
        <Edges threshold={15} color={colors.enclosureEdge} />
      </mesh>
    </group>
  )
}
