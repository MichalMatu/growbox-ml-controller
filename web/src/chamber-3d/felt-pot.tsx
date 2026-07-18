import { useMemo } from "react"
import { DoubleSide, Vector2 } from "three"

import {
  type FeltPotPreset,
  planFeltPotLayout,
  type PotLayoutPlan,
} from "@/chamber-3d/felt-pot-geometry"
import { usePotPbrMaps, type PotPbrMaps } from "@/chamber-3d/pot-pbr"
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
  maps: PotPbrMaps
}

const FELT_NORMAL_SCALE = new Vector2(
  CHAMBER_MATERIAL.potFeltNormalScale,
  CHAMBER_MATERIAL.potFeltNormalScale,
)
const SOIL_NORMAL_SCALE = new Vector2(
  CHAMBER_MATERIAL.potSoilNormalScale,
  CHAMBER_MATERIAL.potSoilNormalScale,
)

/**
 * Soft fabric / felt grow bag: tapered open wall, stitched rim band, soil disc,
 * and two side loop handles. Felt + soil use procedural PBR maps (fiber/grit).
 */
export function FeltPot({ diameterM, heightM, colors, maps }: FeltPotProps) {
  const bottomR = diameterM / 2
  const topR = bottomR * CHAMBER_GEOMETRY.potTopRadiusScale
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimOuterR = topR * (1 + CHAMBER_GEOMETRY.potRimRadiusExtraScale)
  const wallHeight = Math.max(heightM - rimH, heightM * 0.85)
  const wallCenterY = wallHeight / 2
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
      map: maps.felt.map,
      normalMap: maps.felt.normalMap,
      normalScale: FELT_NORMAL_SCALE,
      roughnessMap: maps.felt.roughnessMap,
      roughness: CHAMBER_MATERIAL.potFeltRoughness,
      metalness: CHAMBER_MATERIAL.potFeltMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potFeltEnvMapIntensity,
    }),
    [colors.potFelt, maps.felt],
  )
  const rimMat = useMemo(
    () => ({
      color: colors.potRim,
      map: maps.felt.map,
      normalMap: maps.felt.normalMap,
      normalScale: FELT_NORMAL_SCALE,
      roughnessMap: maps.felt.roughnessMap,
      roughness: CHAMBER_MATERIAL.potFeltRoughness,
      metalness: CHAMBER_MATERIAL.potFeltMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potFeltEnvMapIntensity,
    }),
    [colors.potRim, maps.felt],
  )
  const soilMat = useMemo(
    () => ({
      color: colors.potSoil,
      map: maps.soil.map,
      normalMap: maps.soil.normalMap,
      normalScale: SOIL_NORMAL_SCALE,
      roughnessMap: maps.soil.roughnessMap,
      roughness: CHAMBER_MATERIAL.potSoilRoughness,
      metalness: CHAMBER_MATERIAL.potSoilMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potSoilEnvMapIntensity,
    }),
    [colors.potSoil, maps.soil],
  )

  const wallTopR = bottomR + (topR - bottomR) * (wallHeight / heightM)
  const wallSegs = Math.max(segs, 40)
  const soilSegs = Math.max(segs, 48)

  return (
    <group>
      <mesh castShadow receiveShadow position={[0, wallCenterY, 0]}>
        <cylinderGeometry
          args={[wallTopR, bottomR, wallHeight, wallSegs, 4, true]}
        />
        <meshStandardMaterial {...feltMat} side={DoubleSide} />
      </mesh>

      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[bottomR * 0.98, wallSegs]} />
        <meshStandardMaterial {...feltMat} />
      </mesh>

      <mesh castShadow position={[0, heightM - rimH / 2, 0]}>
        <cylinderGeometry
          args={[rimOuterR, rimOuterR, rimH, wallSegs, 1, true]}
        />
        <meshStandardMaterial {...rimMat} side={DoubleSide} />
      </mesh>
      <mesh
        castShadow
        position={[0, heightM - rimH * 0.15, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[rimOuterR * 0.98, rimH * 0.28, 8, wallSegs]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>

      <mesh
        receiveShadow
        castShadow
        position={[0, Math.max(soilY, wallHeight * 0.7), 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[soilR, soilSegs]} />
        <meshStandardMaterial
          {...soilMat}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
      </mesh>

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
  material: Record<string, unknown>
}) {
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
 * Shared procedural felt/soil PBR maps for all instances.
 */
export function FeltPotGroup({
  widthM,
  depthM,
  heightM,
  preset,
  count,
  colors,
}: FeltPotGroupProps) {
  const maps = usePotPbrMaps(256)
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
          <FeltPot
            diameterM={diameterM}
            heightM={potHeightM}
            colors={colors}
            maps={maps}
          />
        </group>
      ))}
    </group>
  )
}
