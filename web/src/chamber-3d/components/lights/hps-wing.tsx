import { DoubleSide } from "three"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
import { sceneIntensity, useLightMaterials } from "./light-materials"

export function HpsWingMesh({
  lengthM,
  widthM,
  heightM,
  colors,
  lit,
  fixtureShadows,
  powerScale,
  maxReachM,
}: {
  lengthM: number
  widthM: number
  heightM: number
  colors: ChamberSceneColors
  lit: boolean
  fixtureShadows: boolean
  powerScale: number
  maxReachM: number
}) {
  const castShadow = lit && fixtureShadows
  const mats = useLightMaterials(colors, lit)
  const spineW = Math.min(widthM * 0.22, 0.08)
  const spineH = heightM * 0.55
  const wingThick = Math.max(heightM * 0.12, 0.008)
  const wingSpan = (widthM - spineW) / 2
  const topY = heightM / 2
  const spineY = topY - spineH / 2
  const wingY = spineY - spineH * 0.15
  const bulbR = Math.min(lengthM, widthM) * 0.07
  const bulbLen = lengthM * 0.5
  const bulbY = wingY - bulbR * 0.8
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
    CHAMBER_MATERIAL.hpsFillIntensity,
    powerScale,
  )
  const reach = maxReachM
  const sceneColor = colors.lightHpsScene

  return (
    <group>
      <mesh position={[0, spineY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM * 0.9, spineH, spineW]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Wings as reflectors */}
      <mesh
        position={[0, wingY, spineW / 2 + wingSpan / 2]}
        rotation={[0.12, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[0, wingY, -spineW / 2 - wingSpan / 2]}
        rotation={[-0.12, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[0, bulbY, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow={false}
      >
        <capsuleGeometry args={[bulbR, Math.max(0, bulbLen - bulbR * 2), 4, 16]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>

      <pointLight
        position={[0, bulbY, 0]}
        intensity={pointI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-mapSize={[2048, 2048]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0003}
      />
      <spotLight
        position={[0, bulbY, 0]}
        angle={1.25}
        penumbra={0.7}
        intensity={spotI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-mapSize={[2048, 2048]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0003}
      >
        <object3D attach="target" position={[0, bulbY - 1.5, 0]} />
      </spotLight>
      <pointLight
        position={[0, bulbY - 0.08, 0]}
        intensity={fillI}
        distance={Math.min(reach * 0.18, 0.22)}
        decay={2}
        color={sceneColor}
      />
    </group>
  )
}
