import { useMemo } from "react"
import { DoubleSide } from "three"

import {
  type FeltPotPreset,
  planFeltPotLayout,
  type PotLayoutPlan,
} from "@/chamber-3d/felt-pot-geometry"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

export type FeltPotProps = {
  /** Outer diameter (meters). */
  diameterM: number
  /** Wall height (meters). */
  heightM: number
  colors: ChamberSceneColors
}

/**
 * Soft fabric / felt grow bag: tapered open wall, stitched rim band, soil disc,
 * and two side loop handles.
 *
 * Geometry is layered so no two surfaces share a plane (body top cap + rim top
 * used to z-fight and shimmer under orbit / shadows).
 */
export function FeltPot({ diameterM, heightM, colors }: FeltPotProps) {
  const bottomR = diameterM / 2
  const topR = bottomR * CHAMBER_GEOMETRY.potTopRadiusScale
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimOuterR = topR * (1 + CHAMBER_GEOMETRY.potRimRadiusExtraScale)
  // Wall stops at the bottom of the rim band (no coplanar top caps).
  const wallHeight = Math.max(heightM - rimH, heightM * 0.85)
  const wallCenterY = wallHeight / 2
  // Soil clearly below the rim ring.
  const soilY = heightM - rimH - heightM * CHAMBER_GEOMETRY.potSoilInsetScale * 0.5
  const soilR = topR * 0.9
  const segs = CHAMBER_GEOMETRY.potWallSegments
  const handleR = diameterM * CHAMBER_GEOMETRY.potHandleRadiusScale
  const handleW = diameterM * CHAMBER_GEOMETRY.potHandleWidthScale
  const handleH = heightM * CHAMBER_GEOMETRY.potHandleHeightScale
  const handleY = heightM - rimH * 0.35

  const feltMat = useMemo(
    () => ({
      color: colors.potFelt,
      roughness: CHAMBER_MATERIAL.potFeltRoughness,
      metalness: CHAMBER_MATERIAL.potFeltMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potFeltEnvMapIntensity,
    }),
    [colors.potFelt],
  )
  const rimMat = useMemo(
    () => ({
      color: colors.potRim,
      roughness: CHAMBER_MATERIAL.potFeltRoughness,
      metalness: CHAMBER_MATERIAL.potFeltMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potFeltEnvMapIntensity,
    }),
    [colors.potRim],
  )
  const soilMat = useMemo(
    () => ({
      color: colors.potSoil,
      roughness: CHAMBER_MATERIAL.potSoilRoughness,
      metalness: CHAMBER_MATERIAL.potSoilMetalness,
      envMapIntensity: 0,
    }),
    [colors.potSoil],
  )

  // Wall radius at the top of the open cylinder (linear taper).
  const wallTopR = bottomR + (topR - bottomR) * (wallHeight / heightM)

  return (
    <group>
      {/* Open wall only — no top cap (that fought with the rim lid). */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, 0]}>
        <cylinderGeometry
          args={[wallTopR, bottomR, wallHeight, segs, 1, true]}
        />
        <meshStandardMaterial {...feltMat} side={DoubleSide} />
      </mesh>

      {/* Bottom disc (replaces closed cylinder cap). */}
      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[bottomR * 0.98, segs]} />
        <meshStandardMaterial {...feltMat} />
      </mesh>

      {/*
        Stitched rim = open band only (no lids). Outer radius > wall so the
        vertical faces never coplanar; sits on top of the wall edge.
      */}
      <mesh castShadow position={[0, heightM - rimH / 2, 0]}>
        <cylinderGeometry
          args={[rimOuterR, rimOuterR, rimH, segs, 1, true]}
        />
        <meshStandardMaterial {...rimMat} side={DoubleSide} />
      </mesh>
      {/* Thin outer bead on the rim top edge (torus) — single surface, no cap fight. */}
      <mesh
        castShadow
        position={[0, heightM - rimH * 0.15, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[rimOuterR * 0.98, rimH * 0.28, 8, segs]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>

      {/* Soil surface — well below rim, slightly smaller than inner wall. */}
      <mesh
        receiveShadow
        position={[0, Math.max(soilY, wallHeight * 0.7), 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[soilR, segs]} />
        <meshStandardMaterial
          {...soilMat}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
      </mesh>

      {/* Fabric loop handles on left / right (±X), classic grow-bag look */}
      <HandleLoop
        y={handleY}
        x={topR * 0.98}
        z={0}
        width={handleW}
        height={handleH}
        tubeR={handleR}
        yaw={Math.PI / 2}
        material={rimMat}
      />
      <HandleLoop
        y={handleY}
        x={-topR * 0.98}
        z={0}
        width={handleW}
        height={handleH}
        tubeR={handleR}
        yaw={-Math.PI / 2}
        material={rimMat}
      />
    </group>
  )
}

function HandleLoop({
  x,
  y,
  z,
  width,
  height,
  tubeR,
  yaw,
  material,
}: {
  x: number
  y: number
  z: number
  width: number
  height: number
  tubeR: number
  yaw: number
  material: {
    color: string
    roughness: number
    metalness: number
    envMapIntensity: number
  }
}) {
  // Three short segments form a soft rectangular fabric loop.
  const halfW = width / 2
  return (
    <group position={[x, y, z]} rotation={[0, yaw, 0]}>
      <mesh castShadow position={[0, height / 2, 0]}>
        <boxGeometry args={[width, tubeR * 2, tubeR * 2]} />
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh castShadow position={[-halfW, height / 4, 0]}>
        <boxGeometry args={[tubeR * 2, height / 2, tubeR * 2]} />
        <meshStandardMaterial {...material} />
      </mesh>
      <mesh castShadow position={[halfW, height / 4, 0]}>
        <boxGeometry args={[tubeR * 2, height / 2, tubeR * 2]} />
        <meshStandardMaterial {...material} />
      </mesh>
    </group>
  )
}

export type FeltPotGroupProps = {
  widthM: number
  depthM: number
  heightM: number
  preset: FeltPotPreset
  count: number
  colors: ChamberSceneColors
}

/**
 * Places 0–N felt pots on the tent floor according to the packing plan.
 * Only pots that fit are rendered.
 */
export function FeltPotGroup({
  widthM,
  depthM,
  heightM,
  preset,
  count,
  colors,
}: FeltPotGroupProps) {
  const plan: PotLayoutPlan = useMemo(
    () =>
      planFeltPotLayout(
        widthM,
        depthM,
        heightM,
        { diameterCm: preset.diameterCm, heightCm: preset.heightCm },
        count,
      ),
    [widthM, depthM, heightM, preset.diameterCm, preset.heightCm, count],
  )

  const diameterM = preset.diameterCm / 100
  const potHeightM = preset.heightCm / 100

  if (plan.positions.length === 0) return null

  return (
    <group>
      {plan.positions.map((pos, index) => (
        <group key={index} position={[pos.x, 0, pos.z]}>
          <FeltPot diameterM={diameterM} heightM={potHeightM} colors={colors} />
        </group>
      ))}
    </group>
  )
}
