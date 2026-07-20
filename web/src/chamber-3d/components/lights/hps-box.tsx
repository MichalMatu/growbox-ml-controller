import { DoubleSide } from "three"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
import { sceneIntensity, useLightMaterials } from "./light-materials"

export function HpsBoxMesh({
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
  const wall = Math.min(lengthM, widthM, heightM) * 0.08
  const cavityH = heightM * 0.55
  const roofH = heightM * 0.28
  const topY = heightM / 2
  const roofCenterY = topY - roofH / 2
  const cavityCenterY = roofCenterY - roofH / 2 - cavityH / 2
  const bulbLen = Math.min(lengthM, widthM) * 0.55
  const bulbR = Math.min(lengthM, widthM) * 0.08
  const bulbY = cavityCenterY + cavityH * 0.1
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
      <mesh position={[0, roofCenterY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM, roofH, widthM]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Inner reflector faces (open box hood) */}
      <mesh
        position={[0, cavityCenterY, widthM / 2 - wall / 2]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM, cavityH, wall]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[0, cavityCenterY, -widthM / 2 + wall / 2]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM, cavityH, wall]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[lengthM / 2 - wall / 2, cavityCenterY, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[wall, cavityH, widthM - 2 * wall]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[-lengthM / 2 + wall / 2, cavityCenterY, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[wall, cavityH, widthM - 2 * wall]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      {/* Ceiling of cavity — reflective */}
      <mesh
        position={[0, roofCenterY - roofH / 2 - 0.002, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.96, 0.004, widthM * 0.96]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      {/* Single HPS source */}
      <mesh
        position={[0, bulbY, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow={false}
      >
        <capsuleGeometry args={[bulbR, Math.max(0, bulbLen - bulbR * 2), 4, 16]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>
      <mesh position={[0, topY - heightM * 0.02, 0]} castShadow>
        <boxGeometry args={[lengthM * 0.35, heightM * 0.06, widthM * 0.25]} />
        <meshStandardMaterial {...mats.housing} />
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
        position={[0, bulbY - bulbR * 0.2, 0]}
        angle={0.9}
        penumbra={0.4}
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
      {/* Tight residual under hood — short range, less wall milk */}
      <pointLight
        position={[0, cavityCenterY - cavityH * 0.35, 0]}
        intensity={fillI}
        distance={Math.min(reach * 0.18, 0.22)}
        decay={2}
        color={sceneColor}
      />
    </group>
  )
}
