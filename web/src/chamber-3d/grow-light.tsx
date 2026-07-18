import { useLayoutEffect, useMemo, useRef } from "react"
import { DoubleSide, Object3D, type InstancedMesh } from "three"

import {
  type LightPlacementM,
  type LightPreset,
} from "@/chamber-3d/light-geometry"
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
}

const _diodeDummy = new Object3D()

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
}: GrowLightProps) {
  if (preset.form === "none") return null

  const lengthM = preset.lengthCm / 100
  const widthM = preset.widthCm / 100
  const heightM = preset.heightCm / 100

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
        />
      ) : null}
      {preset.form === "hps_box" ? (
        <HpsBoxMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
        />
      ) : null}
      {preset.form === "hps_wing" ? (
        <HpsWingMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
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
      /** Specular mylar / polished aluminium inside HPS reflectors */
      reflector: {
        color: colors.lightDuct,
        roughness: lit ? 0.14 : 0.35,
        metalness: lit ? 0.92 : 0.7,
        envMapIntensity: lit ? 1.55 : 0.55,
        emissive: colors.lightBulb,
        emissiveIntensity: lit ? 0.12 : 0,
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

function sceneIntensity(lit: boolean, on: number): number {
  return lit ? on : CHAMBER_MATERIAL.lightOffSceneIntensity
}

function LedPanelMesh({
  lengthM,
  widthM,
  heightM,
  colors,
  lit,
}: {
  lengthM: number
  widthM: number
  heightM: number
  colors: ChamberSceneColors
  lit: boolean
}) {
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

  /** A few fill points under the panel (not one per diode — GPU budget). */
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
    sceneIntensity(lit, CHAMBER_MATERIAL.ledPanelFillIntensity) /
    fillLights.length
  const spotI = sceneIntensity(lit, CHAMBER_MATERIAL.ledPanelSpotIntensity)
  const lightY = diodeY - 0.02
  const reach = Math.max(lengthM, widthM, 0.6) * 4

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

      {/* Soft multi-point fill from the whole panel face */}
      {fillLights.map((p, i) => (
        <pointLight
          key={i}
          position={[p.x, lightY, p.z]}
          intensity={fillEach}
          distance={reach}
          decay={2}
          color={colors.lightEmitter}
        />
      ))}
      {/* Broad downward wash so canopy / pots read clearly when ON */}
      <spotLight
        position={[0, lightY, 0]}
        angle={1.05}
        penumbra={0.65}
        intensity={spotI}
        distance={reach * 1.2}
        decay={2}
        color={colors.lightEmitter}
        castShadow={lit}
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
}: {
  lengthM: number
  widthM: number
  heightM: number
  colors: ChamberSceneColors
  lit: boolean
}) {
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
  const pointI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsPointIntensity)
  const spotI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsSpotIntensity)
  const fillI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsFillIntensity)
  const reach = Math.max(lengthM, widthM, heightM) * 5

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
        castShadow
      >
        <cylinderGeometry args={[bulbR, bulbR, bulbLen, 16]} />
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
        color={colors.lightBulb}
        castShadow={lit}
      />
      <spotLight
        position={[0, bulbY - bulbR * 0.2, 0]}
        angle={0.85}
        penumbra={0.45}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={colors.lightBulb}
        castShadow={lit}
      >
        <object3D attach="target" position={[0, bulbY - 1.5, 0]} />
      </spotLight>
      {/* Soft bounce fill under the hood (reflector “glow”) */}
      <pointLight
        position={[0, cavityCenterY - cavityH * 0.35, 0]}
        intensity={fillI}
        distance={reach * 0.7}
        decay={2}
        color={colors.lightEmitter}
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
}: {
  lengthM: number
  widthM: number
  heightM: number
  colors: ChamberSceneColors
  lit: boolean
}) {
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
  const bulbY = wingY - heightM * 0.05
  const pointI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsPointIntensity)
  const spotI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsSpotIntensity * 0.9)
  const fillI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsFillIntensity)
  const reach = Math.max(lengthM, widthM) * 5

  return (
    <group>
      <mesh position={[0, spineY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM * 0.9, spineH, spineW]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Wings as reflectors */}
      <mesh
        position={[0, wingY, spineW / 2 + wingSpan / 2]}
        rotation={[0.18, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[0, wingY, -spineW / 2 - wingSpan / 2]}
        rotation={[-0.18, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.reflector} side={DoubleSide} />
      </mesh>
      <mesh
        position={[0, bulbY, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[bulbR, bulbR, bulbLen, 16]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>

      <pointLight
        position={[0, bulbY, 0]}
        intensity={pointI}
        distance={reach}
        decay={2}
        color={colors.lightBulb}
        castShadow={lit}
      />
      <spotLight
        position={[0, bulbY, 0]}
        angle={1.0}
        penumbra={0.55}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={colors.lightBulb}
      >
        <object3D attach="target" position={[0, bulbY - 1.5, 0]} />
      </spotLight>
      <pointLight
        position={[0, bulbY - 0.08, 0]}
        intensity={fillI}
        distance={reach * 0.65}
        decay={2}
        color={colors.lightEmitter}
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
}: {
  lengthM: number
  widthM: number
  heightM: number
  ductDiameterCm: number
  colors: ChamberSceneColors
  lit: boolean
}) {
  const mats = useLightMaterials(colors, lit)
  const tubeR = Math.min(widthM, heightM) * 0.42
  const tubeLen = lengthM * 0.72
  const ductR = ductDiameterCm / 100 / 2
  const flangeLen = lengthM * 0.12
  const pointI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsPointIntensity * 0.85)
  const spotI = sceneIntensity(lit, CHAMBER_MATERIAL.hpsSpotIntensity * 0.75)
  const reach = Math.max(lengthM, widthM, heightM) * 5

  return (
    <group>
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
        <cylinderGeometry args={[tubeR, tubeR, tubeLen, 24]} />
        <meshStandardMaterial
          {...mats.duct}
          transparent
          opacity={0.42}
          roughness={0.12}
          metalness={0.25}
          emissive={colors.lightBulb}
          emissiveIntensity={lit ? 0.2 : 0}
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
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry
          args={[tubeR * 0.28, tubeR * 0.28, tubeLen * 0.45, 14]}
        />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>

      {/* Single source inside the tube */}
      <pointLight
        position={[0, 0, 0]}
        intensity={pointI}
        distance={reach}
        decay={2}
        color={colors.lightBulb}
        castShadow={lit}
      />
      <spotLight
        position={[0, -tubeR * 0.15, 0]}
        angle={0.95}
        penumbra={0.5}
        intensity={spotI}
        distance={reach}
        decay={2}
        color={colors.lightBulb}
      >
        <object3D attach="target" position={[0, -1.5, 0]} />
      </spotLight>
    </group>
  )
}
