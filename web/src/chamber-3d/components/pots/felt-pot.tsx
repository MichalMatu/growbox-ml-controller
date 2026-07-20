import { useMemo } from "react"
import { DoubleSide, Vector2 } from "three"

import {
  type FeltPotPreset,
  planFeltPotLayout,
  type PotLayoutPlan,
} from "@/chamber-3d/components/pots/felt-pot-geometry"
import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { usePotPbrMaps, type PotPbrMaps } from "@/chamber-3d/materials/pot-pbr"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/core/scene-tokens"

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

/**
 * Soft fabric / felt grow bag: open top (no lid/cover), stitched rim bead,
 * recessed soil surface. No side handles (real fabric pots are plain bags).
 *
 * Layout (Y up, base at 0):
 *   wall:  open cylinder [0, heightM] — never a top cap / lid
 *   rim:   open band + torus bead only (no disc covering the mouth)
 *   soil:  recessed disc below the lip (open bag, not a flush lid plug)
 *
 * Historical bug: wall top cap / rim “lid” coplanar fights. Do not re-add
 * any horizontal felt mesh that spans the pot opening.
 */
export function FeltPot({ diameterM, heightM, colors, maps }: FeltPotProps) {
  const { config } = useChamberPerformance()
  const segs = config.potWallSegments
  const bottomR = diameterM / 2
  const topR = bottomR * CHAMBER_GEOMETRY.potTopRadiusScale
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimOuterR = topR * (1 + CHAMBER_GEOMETRY.potRimRadiusExtraScale)
  // Wall runs full bag height so felt texture reaches the lip (under the rim).
  const wallHeight = heightM
  const wallCenterY = wallHeight / 2
  const wallTopR = topR
  // Lower the rim onto the wall: most of the band sits below heightM.
  const rimCenterY = heightM - rimH * 0.65
  const rimTopY = rimCenterY + rimH / 2
  // Soil clearly recessed under the open lip (open bag, not a sealed lid).
  const soilInset = Math.max(
    heightM * CHAMBER_GEOMETRY.potSoilInsetScale,
    0.012,
  )
  const soilY = Math.min(
    rimCenterY - rimH * 0.35 - soilInset,
    heightM * 0.82,
  )
  const wallTaper = wallHeight > 0 ? soilY / wallHeight : 1
  const wallRAtSoil = bottomR + (wallTopR - bottomR) * wallTaper
  // Slightly under wall radius avoids z-fight at the soil–wall join.
  const soilR = wallRAtSoil * 0.988

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
  const wallSegs = Math.max(segs, 40)
  const soilSegs = Math.max(segs, 48)
  // Inner liner only up to the soil plane — open above so the bag mouth is empty.
  const linerInset = Math.max(diameterM * 0.012, 0.0025)
  const linerBottomR = Math.max(bottomR - linerInset, bottomR * 0.94)
  const linerTopR = Math.max(
    wallRAtSoil - linerInset,
    wallRAtSoil * 0.94,
  )
  const linerHeight = Math.max(soilY - 0.003, heightM * 0.35)
  const linerCenterY = linerHeight / 2

  return (
    <group>
      {/* Outer wall — open ends only. Never add a top cap (that was the “lid”). */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, 0]}>
        <cylinderGeometry
          args={[wallTopR, bottomR, wallHeight, wallSegs, 4, true]}
        />
        <meshStandardMaterial {...feltMat} side={DoubleSide} />
      </mesh>

      {/* Inner liner below soil — open tube, no top disc. */}
      <mesh position={[0, linerCenterY, 0]}>
        <cylinderGeometry
          args={[linerTopR, linerBottomR, linerHeight, wallSegs, 1, true]}
        />
        <meshStandardMaterial {...feltMat} side={DoubleSide} />
      </mesh>

      {/* Bag floor only (bottom) — not a top cover. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[bottomR * 0.98, wallSegs]} />
        <meshStandardMaterial {...feltMat} />
      </mesh>

      {/* Rim = open band + bead. No horizontal felt disc over the mouth. */}
      <mesh castShadow position={[0, rimCenterY, 0]}>
        <cylinderGeometry
          args={[rimOuterR, rimOuterR, rimH, wallSegs, 1, true]}
        />
        <meshStandardMaterial {...rimMat} side={DoubleSide} />
      </mesh>
      <mesh
        castShadow
        position={[0, rimTopY - rimH * 0.08, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <torusGeometry args={[rimOuterR * 0.98, rimH * 0.28, 8, wallSegs]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>

      {/*
        Soil surface: recessed disc. MeshBasicMaterial + absolute albedo map
        so black potting mix is not gray-washed by cool lights / ACES.
      */}
      <mesh
        castShadow
        receiveShadow
        position={[0, soilY, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <circleGeometry args={[soilR, soilSegs]} />
        <meshBasicMaterial
          map={maps.soil.map}
          color={colors.potSoil}
          toneMapped={false}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
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
  const { config } = useChamberPerformance()
  const maps = usePotPbrMaps(config.potPbrSize)
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
