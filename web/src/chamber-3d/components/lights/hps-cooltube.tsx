import { DoubleSide } from "three"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
import { sceneIntensity, useLightMaterials } from "./light-materials"

export function HpsCooltubeMesh({
  lengthM,
  widthM,
  heightM,
  ductDiameterCm,
  colors,
  lit,
  fixtureShadows,
  powerScale,
  maxReachM,
}: {
  lengthM: number
  widthM: number
  heightM: number
  ductDiameterCm: number
  colors: ChamberSceneColors
  lit: boolean
  fixtureShadows: boolean
  powerScale: number
  maxReachM: number
}) {
  const castShadow = lit && fixtureShadows
  const mats = useLightMaterials(colors, lit)
  const tubeR = Math.min(widthM, heightM) * 0.42
  const tubeLen = lengthM * 0.72
  const ductR = ductDiameterCm / 100 / 2
  const flangeLen = lengthM * 0.12
  const pointI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.hpsPointIntensity,
    powerScale,
  )
  const spotI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.hpsSpotIntensity,
    powerScale,
  )
  const fillI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.hpsFillIntensity * 0.7,
    powerScale,
  )
  const reach = maxReachM
  const sceneColor = colors.lightHpsScene

  return (
    <group>
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow={false} receiveShadow>
        <cylinderGeometry args={[tubeR, tubeR, tubeLen, 24, 1, true]} />
        <meshStandardMaterial
          {...mats.duct}
          transparent
          opacity={0.42}
          roughness={0.12}
          metalness={0.25}
          emissive={colors.lightBulb}
          emissiveIntensity={lit ? 0.12 : 0}
          side={DoubleSide}
        />
      </mesh>
      <mesh
        position={[tubeLen / 2 + flangeLen / 2, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow={false}
      >
        <cylinderGeometry args={[ductR, ductR, flangeLen, 20, 1, true]} />
        <meshStandardMaterial {...mats.duct} side={DoubleSide} />
      </mesh>
      <mesh
        position={[-tubeLen / 2 - flangeLen / 2, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow={false}
      >
        <cylinderGeometry args={[ductR, ductR, flangeLen, 20, 1, true]} />
        <meshStandardMaterial {...mats.duct} side={DoubleSide} />
      </mesh>
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow={false}>
        <capsuleGeometry
          args={[tubeR * 0.28, Math.max(0, tubeLen * 0.45 - tubeR * 0.56), 4, 14]}
        />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>

      <pointLight
        position={[0, 0, 0]}
        intensity={pointI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-mapSize={[2048, 2048]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0001}
      />
      <spotLight
        position={[0, -tubeR * 0.15, 0]}
        angle={0.95}
        penumbra={0.5}
        intensity={spotI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-mapSize={[2048, 2048]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0001}
      >
        <object3D attach="target" position={[0, -1.5, 0]} />
      </spotLight>
      <pointLight
        position={[0, -tubeR * 0.35, 0]}
        intensity={fillI}
        distance={Math.min(reach * 0.18, 0.22)}
        decay={2}
        color={sceneColor}
      />
    </group>
  )
}
