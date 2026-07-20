import { useLayoutEffect, useMemo, useRef } from "react"
import { DoubleSide, Object3D, type InstancedMesh } from "three"

import {
  type LightForm,
  type LightPlacementM,
  type LightPreset,
} from "@/chamber-3d/light-geometry"
import { useChamberPerformance } from "@/chamber-3d/performance-context"
import {
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

export type GrowLightProps = {
  preset: LightPreset
  placement: LightPlacementM
  colors: ChamberSceneColors
  /** When true, diodes/bulb glow and real scene lights turn on. */
  lit?: boolean
  /** Tent AABB (meters) — clamps light distance to the interior volume. */
  tentWidthM: number
  tentDepthM: number
  tentHeightM: number
}

/**
 * Max useful reach from a ceiling fixture to the far interior corner.
 * Prevents multi-meter fixture “reach” spheres that light the stage pad
 * (layers also isolate the pad; distance keeps falloff natural inside).
 */
function interiorLightReachM(
  tentWidthM: number,
  tentDepthM: number,
  lightWorldY: number,
): number {
  const halfW = tentWidthM * 0.5
  const halfD = tentDepthM * 0.5
  const toFarCorner = Math.hypot(halfW, halfD, Math.max(lightWorldY, 0.15))
  return toFarCorner * 1.1
}

const _diodeDummy = new Object3D()

/**
 * Soft power curve so 1000 W reads stronger than 600 W without blowing foil.
 * Reference watts live in CHAMBER_MATERIAL (LED 200 / HPS 600).
 */
function fixturePowerScale(preset: LightPreset): number {
  if (preset.form === "none" || preset.powerW <= 0) return 0
  const refW =
    preset.form === "led_panel"
      ? CHAMBER_MATERIAL.ledPowerRefW
      : CHAMBER_MATERIAL.hpsPowerRefW
  return Math.sqrt(preset.powerW / refW)
}

function hpsFormScale(form: LightForm): number {
  switch (form) {
    case "hps_box":
      return CHAMBER_MATERIAL.hpsFormScaleBox
    case "hps_wing":
      return CHAMBER_MATERIAL.hpsFormScaleWing
    case "hps_cooltube":
      return CHAMBER_MATERIAL.hpsFormScaleCooltube
    default:
      return 1
  }
}

/**
 * Parametric grow-light fixture from catalog AABB.
 * LED: diode grid + multi-point fill from the panel face.
 * HPS: single bulb source + spot + reflective hood/wing materials.
 * Local space: length +X, width +Z, height +Y; group applies yaw.
 */
export function GrowLight({
  preset,
  placement,
  colors,
  lit = true,
  tentWidthM,
  tentDepthM,
  tentHeightM,
}: GrowLightProps) {
  const { config } = useChamberPerformance()

  if (preset.form === "none") return null

  const lengthM = preset.lengthCm / 100
  const widthM = preset.widthCm / 100
  const heightM = preset.heightCm / 100
  const powerScale = fixturePowerScale(preset)
  const formScale = hpsFormScale(preset.form)
  // Emitter sits near the bottom of the AABB; world Y ≈ placement.y - body/2.
  const emitterWorldY = Math.max(
    0.12,
    placement.y - heightM * 0.35,
  )
  const maxReachM = interiorLightReachM(
    tentWidthM,
    tentDepthM,
    emitterWorldY,
  )
  void tentHeightM

  return (
    <group
      position={[placement.x, placement.y, placement.z]}
      rotation={[0, placement.rotationYRad, 0]}
    >
      {preset.form === "led_panel" ? (
        <LedPanelMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale}
          maxReachM={maxReachM}
        />
      ) : null}
      {preset.form === "hps_box" ? (
        <HpsBoxMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
      {preset.form === "hps_wing" ? (
        <HpsWingMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
      {preset.form === "hps_cooltube" ? (
        <HpsCooltubeMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          ductDiameterCm={preset.ductDiameterCm ?? 12.5}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
    </group>
  )
}

function useLightMaterials(colors: ChamberSceneColors, lit: boolean) {
  return useMemo(
    () => ({
      housing: {
        color: colors.lightHousing,
        roughness: CHAMBER_MATERIAL.lightHousingRoughness,
        metalness: CHAMBER_MATERIAL.lightHousingMetalness,
        envMapIntensity: CHAMBER_MATERIAL.lightHousingEnvMapIntensity,
      },
      /** Specular aluminium inside HPS reflectors — no warm emissive wash. */
      reflector: {
        color: colors.lightDuct,
        roughness: 0.2,
        metalness: 0.9,
        envMapIntensity: 0.8,
      },
      board: {
        color: colors.lightHousing,
        roughness: 0.75,
        metalness: 0.25,
        envMapIntensity: 0.25,
      },
      diode: {
        color: colors.lightEmitter,
        roughness: 0.2,
        metalness: 0.05,
        emissive: colors.lightEmitter,
        emissiveIntensity: lit
          ? CHAMBER_MATERIAL.lightEmitterEmissiveOn
          : CHAMBER_MATERIAL.lightEmitterEmissiveOff,
      },
      duct: {
        color: colors.lightDuct,
        roughness: CHAMBER_MATERIAL.lightDuctRoughness,
        metalness: CHAMBER_MATERIAL.lightDuctMetalness,
        envMapIntensity: 0.85,
      },
      bulb: {
        color: colors.lightBulb,
        roughness: 0.18,
        metalness: 0.05,
        emissive: colors.lightBulb,
        emissiveIntensity: lit
          ? CHAMBER_MATERIAL.lightBulbEmissiveOn
          : CHAMBER_MATERIAL.lightBulbEmissiveOff,
      },
    }),
    [colors, lit],
  )
}

function sceneIntensity(lit: boolean, on: number, powerScale: number): number {
  if (!lit) return CHAMBER_MATERIAL.lightOffSceneIntensity
  return on * powerScale
}

function LedPanelMesh({
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
  const castSpotShadow = lit && fixtureShadows
  const mats = useLightMaterials(colors, lit)
  const bodyH = heightM * 0.72
  const plateH = heightM * 0.18
  const topY = heightM / 2
  const housingCenterY = topY - bodyH / 2
  const plateCenterY = housingCenterY - bodyH / 2 - plateH / 2 - 0.001
  const diodeY = plateCenterY - plateH / 2 - 0.002

  const diodeGrid = useMemo(() => {
    const pitch = CHAMBER_MATERIAL.ledDiodePitchM
    const maxAxis = CHAMBER_MATERIAL.ledDiodeMaxAxis
    const usableL = lengthM * 0.9
    const usableW = widthM * 0.9
    const cols = Math.min(
      maxAxis,
      Math.max(4, Math.floor(usableL / pitch)),
    )
    const rows = Math.min(
      maxAxis,
      Math.max(3, Math.floor(usableW / pitch)),
    )
    const spanX = (cols - 1) * pitch
    const spanZ = (rows - 1) * pitch
    const originX = -spanX / 2
    const originZ = -spanZ / 2
    const radius =
      pitch * CHAMBER_MATERIAL.ledDiodeRadiusScale * 0.5
    const positions: { x: number; z: number }[] = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        positions.push({
          x: originX + c * pitch,
          z: originZ + r * pitch,
        })
      }
    }
    return { cols, rows, positions, radius, pitch }
  }, [lengthM, widthM])

  const diodeMeshRef = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const mesh = diodeMeshRef.current
    if (!mesh) return
    const { positions } = diodeGrid
    for (let i = 0; i < positions.length; i++) {
      const p = positions[i]!
      _diodeDummy.position.set(p.x, 0, p.z)
      _diodeDummy.scale.set(1, 1, 1)
      _diodeDummy.updateMatrix()
      mesh.setMatrixAt(i, _diodeDummy.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
    mesh.count = positions.length
  }, [diodeGrid])

  /** Sparse local fill only — bulk light is the broad spot (less milky mylar). */
  const fillLights = useMemo(() => {
    const insetX = lengthM * 0.28
    const insetZ = widthM * 0.28
    return [
      { x: 0, z: 0 },
      { x: -insetX, z: -insetZ },
      { x: insetX, z: -insetZ },
      { x: -insetX, z: insetZ },
      { x: insetX, z: insetZ },
    ] as const
  }, [lengthM, widthM])

  const fillEach =
    sceneIntensity(lit, CHAMBER_MATERIAL.ledPanelFillIntensity, powerScale) /
    fillLights.length
  const spotI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.ledPanelSpotIntensity,
    powerScale,
  )
  const lightY = diodeY - 0.02
  const reach = maxReachM
  const sceneColor = colors.lightLedScene

  return (
    <group>
      <mesh position={[0, housingCenterY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM, bodyH, widthM]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* PCB plate under heatsink */}
      <mesh position={[0, plateCenterY, 0]} castShadow>
        <boxGeometry args={[lengthM * 0.94, plateH, widthM * 0.94]} />
        <meshStandardMaterial {...mats.board} />
      </mesh>
      {/* Individual LED dice */}
      <instancedMesh
        ref={diodeMeshRef}
        args={[undefined, undefined, diodeGrid.positions.length]}
        position={[0, diodeY, 0]}
        castShadow={false}
      >
        <boxGeometry
          args={[
            diodeGrid.radius * 1.6,
            diodeGrid.radius * 0.85,
            diodeGrid.radius * 1.6,
          ]}
        />
        <meshStandardMaterial {...mats.diode} />
      </instancedMesh>

      {fillLights.map((p, i) => (
        <pointLight
          key={i}
          position={[p.x, lightY, p.z]}
          intensity={fillEach}
          distance={Math.min(reach * 0.18, 0.22)}
          decay={2}
          color={sceneColor}
        />
      ))}
      {/* Broad downward wash — main canopy / wall key */}
      <spotLight
        position={[0, lightY, 0]}
        angle={1.15}
        penumbra={0.7}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castSpotShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={reach * 1.15}
        shadow-bias={-0.00025}
      >
        <object3D attach="target" position={[0, lightY - 1.5, 0]} />
      </spotLight>
    </group>
  )
}

function HpsBoxMesh({
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
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
        shadow-bias={-0.0003}
      />
      <spotLight
        position={[0, bulbY - bulbR * 0.2, 0]}
        angle={0.9}
        penumbra={0.4}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
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

function HpsWingMesh({
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
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
        shadow-bias={-0.0003}
      />
      <spotLight
        position={[0, bulbY, 0]}
        angle={1.25}
        penumbra={0.7}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
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

function HpsCooltubeMesh({
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
        <cylinderGeometry args={[tubeR, tubeR, tubeLen, 24]} />
        <meshStandardMaterial
          {...mats.duct}
          transparent
          opacity={0.42}
          roughness={0.12}
          metalness={0.25}
          emissive={colors.lightBulb}
          emissiveIntensity={lit ? 0.12 : 0}
        />
      </mesh>
      <mesh
        position={[tubeLen / 2 + flangeLen / 2, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[ductR, ductR, flangeLen, 20]} />
        <meshStandardMaterial {...mats.duct} />
      </mesh>
      <mesh
        position={[-tubeLen / 2 - flangeLen / 2, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[ductR, ductR, flangeLen, 20]} />
        <meshStandardMaterial {...mats.duct} />
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
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
        shadow-bias={-0.0003}
      />
      <spotLight
        position={[0, -tubeR * 0.15, 0]}
        angle={0.95}
        penumbra={0.5}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={sceneColor}
        castShadow={castShadow}
        shadow-camera-near={0.02}
        shadow-camera-far={Math.max(reach * 1.2, 3.0)}
        shadow-bias={-0.0003}
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
