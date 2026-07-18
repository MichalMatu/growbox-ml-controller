import { Edges } from "@react-three/drei"
import { DoubleSide } from "three"

export type EnclosureDimensions = {
  widthCm: number
  depthCm: number
  heightCm: number
}

/**
 * Parametric grow tent shell. Schema units are cm; scene units are meters.
 * Not wired to the configurator export — preview-only playground.
 */
export function Enclosure({ widthCm, depthCm, heightCm }: EnclosureDimensions) {
  const widthM = Math.max(widthCm, 1) / 100
  const depthM = Math.max(depthCm, 1) / 100
  const heightM = Math.max(heightCm, 1) / 100

  return (
    <group position={[0, heightM / 2, 0]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[widthM, heightM, depthM]} />
        <meshStandardMaterial
          color="#4ade80"
          transparent
          opacity={0.18}
          side={DoubleSide}
          depthWrite={false}
        />
        <Edges threshold={15} color="#22c55e" />
      </mesh>
    </group>
  )
}
