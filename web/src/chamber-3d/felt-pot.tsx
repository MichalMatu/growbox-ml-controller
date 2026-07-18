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
 * Soft fabric / felt grow bag: full-height tapered wall, stitched rim band
 * overlapping the wall top, sealed soil plug, side loop handles.
 * Felt + soil use procedural PBR maps (fiber/grit).
 *
 * Relative layout (Y up, base at 0) — must stay consistent:
 *   wall:  y ∈ [0, heightM], open cylinder, top radius = topR
 *   rim:   band lowered onto wall (overlap) so fabric UV continues under it
 *   soil:  top just below rim; radius = wall radius at soilY (not a smaller disc)
 *
 * Prior bug: wall stopped at heightM−rimH with radius ≠ rim, soil at topR×0.9
 * → annular gap and radial step at the rim → show-through from inside.
 */
export function FeltPot({ diameterM, heightM, colors, maps }: FeltPotProps) {
  const bottomR = diameterM / 2
  const topR = bottomR * CHAMBER_GEOMETRY.potTopRadiusScale
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimOuterR = topR * (1 + CHAMBER_GEOMETRY.potRimRadiusExtraScale)
  // Wall runs full bag height so felt texture reaches the lip (under the rim).
  const wallHeight = heightM
  const wallCenterY = wallHeight / 2
  const wallTopR = topR
  // Lower the rim onto the wall: most of the band sits below heightM.
  // rim top ≈ heightM − rimH×0.15, rim bottom ≈ heightM − rimH×1.15 (overlap).
  const rimCenterY = heightM - rimH * 0.65
  const rimTopY = rimCenterY + rimH / 2
  // Soil surface just under the rim inner lip; match wall radius at that Y.
  const soilInset = Math.max(
    heightM * CHAMBER_GEOMETRY.potSoilInsetScale * 0.35,
    0.004,
  )
  const soilY = Math.min(rimCenterY - rimH * 0.15 - soilInset, heightM * 0.94)
  const wallTaper = wallHeight > 0 ? soilY / wallHeight : 1
  const wallRAtSoil = bottomR + (wallTopR - bottomR) * wallTaper
  // Slightly under wall radius avoids z-fight; still seals the annular gap.
  const soilR = wallRAtSoil * 0.992
  const soilThickness = Math.max(heightM * 0.045, 0.01)
  const soilCenterY = Math.max(soilY - soilThickness / 2, soilThickness / 2)
  const segs = CHAMBER_GEOMETRY.potWallSegments
  const handleR = diameterM * CHAMBER_GEOMETRY.potHandleRadiusScale
  const handleW = diameterM * CHAMBER_GEOMETRY.potHandleWidthScale
  const handleH = heightM * CHAMBER_GEOMETRY.potHandleHeightScale
  const handleY = rimCenterY

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

  const wallSegs = Math.max(segs, 40)
  const soilSegs = Math.max(segs, 48)
  // Inner liner: closed felt skin just inside the wall so camera rays from
  // inside never fall through a zero-thickness DoubleSide shell.
  const linerInset = Math.max(diameterM * 0.012, 0.0025)
  const linerBottomR = Math.max(bottomR - linerInset, bottomR * 0.94)
  const linerTopR = Math.max(topR - linerInset, topR * 0.94)
  const linerHeight = Math.max(soilY - 0.002, heightM * 0.5)
  const linerCenterY = linerHeight / 2

  return (
    <group>
      {/* Outer wall — full height, open ends; fabric UV runs under the rim. */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, 0]}>
        <cylinderGeometry
          args={[wallTopR, bottomR, wallHeight, wallSegs, 4, true]}
        />
        <meshStandardMaterial {...feltMat} side={DoubleSide} />
      </mesh>

      {/* Inner liner — FrontSide only, seals interior show-through. */}
      <mesh position={[0, linerCenterY, 0]}>
        <cylinderGeometry
          args={[linerTopR, linerBottomR, linerHeight, wallSegs, 1, true]}
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

      {/* Rim band lowered onto wall (overlap), not stacked above a shorter wall. */}
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

      {/* Soil plug: radius matches wall at soilY; short height blocks under-disc gaps. */}
      <mesh castShadow receiveShadow position={[0, soilCenterY, 0]}>
        <cylinderGeometry
          args={[soilR, soilR * 0.98, soilThickness, soilSegs, 1, false]}
        />
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
