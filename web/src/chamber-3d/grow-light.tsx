import { useMemo } from "react"

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
  /** When true, emitter is brighter (playground “on”). */
  lit?: boolean
}

/**
 * Parametric grow-light fixture from catalog AABB.
 * Forms: LED panel/bar, HPS box hood, HPS wing, HPS cooltube — no bell shapes.
 * Local space: length along +X, width along +Z, height along +Y; group applies yaw.
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
      emitter: {
        color: colors.lightEmitter,
        roughness: 0.35,
        metalness: 0.1,
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
        roughness: 0.25,
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
  const plateH = heightM * 0.22
  // Local origin at AABB center.
  const topY = heightM / 2
  const housingCenterY = topY - bodyH / 2
  const plateCenterY = housingCenterY - bodyH / 2 - plateH / 2 - 0.001

  return (
    <group>
      <mesh position={[0, housingCenterY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM, bodyH, widthM]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh position={[0, plateCenterY, 0]} castShadow>
        <boxGeometry args={[lengthM * 0.94, plateH, widthM * 0.94]} />
        <meshStandardMaterial {...mats.emitter} />
      </mesh>
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
  const outerH = heightM
  const cavityH = heightM * 0.55
  const roofH = heightM * 0.28
  const topY = heightM / 2
  const roofCenterY = topY - roofH / 2
  const cavityCenterY = roofCenterY - roofH / 2 - cavityH / 2
  const bulbLen = Math.min(lengthM, widthM) * 0.55
  const bulbR = Math.min(lengthM, widthM) * 0.08

  return (
    <group>
      {/* Roof slab of the box hood */}
      <mesh position={[0, roofCenterY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM, roofH, widthM]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Four side walls — open bottom (box, not bell) */}
      <mesh
        position={[0, cavityCenterY, widthM / 2 - wall / 2]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM, cavityH, wall]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh
        position={[0, cavityCenterY, -widthM / 2 + wall / 2]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM, cavityH, wall]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh
        position={[lengthM / 2 - wall / 2, cavityCenterY, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[wall, cavityH, widthM - 2 * wall]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh
        position={[-lengthM / 2 + wall / 2, cavityCenterY, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[wall, cavityH, widthM - 2 * wall]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Bulb along +X inside cavity */}
      <mesh
        position={[0, cavityCenterY + cavityH * 0.1, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[bulbR, bulbR, bulbLen, 16]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>
      <mesh position={[0, topY - outerH * 0.02, 0]} castShadow>
        <boxGeometry args={[lengthM * 0.35, heightM * 0.06, widthM * 0.25]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
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

  return (
    <group>
      {/* Central spine / lamp holder */}
      <mesh position={[0, spineY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM * 0.9, spineH, spineW]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Left / right wings (flat panels — not a bell) */}
      <mesh
        position={[0, wingY, spineW / 2 + wingSpan / 2]}
        rotation={[0.18, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh
        position={[0, wingY, -spineW / 2 - wingSpan / 2]}
        rotation={[-0.18, 0, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry args={[lengthM * 0.95, wingThick, wingSpan]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh
        position={[0, wingY - heightM * 0.05, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[bulbR, bulbR, bulbLen, 16]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>
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
  const ductR = (ductDiameterCm / 100) / 2
  const flangeLen = lengthM * 0.12
  const wingW = widthM * 0.35
  const wingThick = Math.max(heightM * 0.06, 0.006)

  return (
    <group>
      {/* Main glass/air tube along +X */}
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
        <cylinderGeometry args={[tubeR, tubeR, tubeLen, 24]} />
        <meshStandardMaterial
          {...mats.duct}
          transparent
          opacity={0.55}
          roughness={0.15}
          metalness={0.2}
        />
      </mesh>
      {/* End duct collars */}
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
      {/* Small wing flaps beside tube */}
      <mesh position={[0, tubeR * 0.15, tubeR + wingW / 2]} castShadow>
        <boxGeometry args={[tubeLen * 0.7, wingThick, wingW]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      <mesh position={[0, tubeR * 0.15, -tubeR - wingW / 2]} castShadow>
        <boxGeometry args={[tubeLen * 0.7, wingThick, wingW]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* Bulb inside tube */}
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[tubeR * 0.28, tubeR * 0.28, tubeLen * 0.45, 14]} />
        <meshStandardMaterial {...mats.bulb} />
      </mesh>
    </group>
  )
}
