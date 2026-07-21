import { useMemo } from "react"
import { DoubleSide } from "three"

import {
  type SquarePotPreset,
  planSquarePotLayout,
  type SquarePotLayoutPlan,
} from "@/chamber-3d/components/pots/square-pot-geometry"
import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { usePotPbrMaps, type PotPbrMaps } from "@/chamber-3d/materials/pot-pbr"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/core/scene-tokens"

export type SquarePotProps = {
  /** Outer side length (meters). */
  sideM: number
  /** Wall height (meters). */
  heightM: number
  colors: ChamberSceneColors
  maps: PotPbrMaps
}

/**
 * Rigid square / rectangular plastic grow pot.
 *
 * Layout (Y up, base at 0):
 *   wall:  open box (no top face)
 *   rim:   flat ring at the top opening
 *   soil:  recessed surface below the rim
 */
export function SquarePot({ sideM, heightM, colors, maps }: SquarePotProps) {
  const { config } = useChamberPerformance()

  const halfSide = sideM / 2
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimWidth = sideM * CHAMBER_GEOMETRY.potRimRadiusExtraScale
  const rimOuterHalf = halfSide + rimWidth

  // Wall runs full height so texture reaches the lip (under the rim).
  const wallHeight = heightM
  const wallCenterY = wallHeight / 2

  // Rim sits on top of the wall.
  const rimCenterY = heightM - rimH * 0.65

  // Soil recessed under the open lip.
  const soilInset = Math.max(
    heightM * CHAMBER_GEOMETRY.potSoilInsetScale,
    0.012,
  )
  const soilY = Math.min(
    rimCenterY - rimH * 0.35 - soilInset,
    heightM * 0.82,
  )

  // Inner liner — slightly smaller than outer walls, up to soil level.
  const linerInset = Math.max(sideM * 0.012, 0.0025)
  const linerHalf = Math.max(halfSide - linerInset, halfSide * 0.94)
  const linerHeight = Math.max(soilY - 0.003, heightM * 0.35)
  const linerCenterY = linerHeight / 2

  const wallSegs = Math.max(config.potWallSegments, 24)

  const plasticMat = useMemo(
    () => ({
      color: colors.potFelt,
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
      roughnessMap: maps.felt.roughnessMap,
      roughness: CHAMBER_MATERIAL.potFeltRoughness,
      metalness: CHAMBER_MATERIAL.potFeltMetalness,
      envMapIntensity: CHAMBER_MATERIAL.potFeltEnvMapIntensity,
    }),
    [colors.potRim, maps.felt],
  )

  return (
    <group>
      {/* Outer wall — open box (no top face). */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, 0]}>
        <boxGeometry args={[sideM, wallHeight, sideM, wallSegs, 1, wallSegs]} />
        <meshStandardMaterial {...plasticMat} side={DoubleSide} />
      </mesh>

      {/* Inner liner below soil — open box without top face. */}
      <mesh position={[0, linerCenterY, 0]}>
        <boxGeometry args={[linerHalf * 2, linerHeight, linerHalf * 2, wallSegs, 1, wallSegs]} />
        <meshStandardMaterial {...plasticMat} side={DoubleSide} />
      </mesh>

      {/* Bottom floor. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[sideM * 0.98, sideM * 0.98]} />
        <meshStandardMaterial {...plasticMat} />
      </mesh>

      {/* Rim — open frame at the top. */}
      {/* Rim band: four thin boxes around the top edge */}
      <mesh castShadow position={[0, rimCenterY, 0]}>
        <boxGeometry
          args={[rimOuterHalf * 2 + rimWidth * 2, rimH, rimOuterHalf * 2 + rimWidth * 2, wallSegs, 1, wallSegs]}
        />
        <meshStandardMaterial {...rimMat} side={DoubleSide} />
      </mesh>

      {/* Soil surface: recessed plane. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, soilY, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[halfSide * 2 * 0.94, halfSide * 2 * 0.94]} />
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

export type SquarePotGroupProps = {
  widthM: number
  depthM: number
  heightM: number
  preset: SquarePotPreset
  count: number
  colors: ChamberSceneColors
}

/**
 * Places 0–N square pots on the tent floor according to the packing plan.
 * Shared procedural PBR maps for all instances.
 */
export function SquarePotGroup({
  widthM,
  depthM,
  heightM,
  preset,
  count,
  colors,
}: SquarePotGroupProps) {
  const { config } = useChamberPerformance()
  const maps = usePotPbrMaps(config.potPbrSize)
  const plan: SquarePotLayoutPlan = useMemo(
    () =>
      planSquarePotLayout(
        widthM,
        depthM,
        heightM,
        { sideCm: preset.sideCm, heightCm: preset.heightCm },
        count,
      ),
    [widthM, depthM, heightM, preset.sideCm, preset.heightCm, count],
  )

  const sideM = preset.sideCm / 100
  const potHeightM = preset.heightCm / 100

  if (plan.positions.length === 0) return null

  return (
    <group>
      {plan.positions.map((pos, index) => (
        <group key={index} position={[pos.x, 0, pos.z]}>
          <SquarePot
            sideM={sideM}
            heightM={potHeightM}
            colors={colors}
            maps={maps}
          />
        </group>
      ))}
    </group>
  )
}
