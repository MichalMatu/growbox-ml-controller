import { useMemo } from "react"

import {
  type SquarePotPreset,
  planSquarePotLayout,
  type SquarePotLayoutPlan,
} from "@/chamber-3d/components/pots/square-pot-geometry"
import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import {
  createPlasticPbrMaps,
  type PlasticPbrMaps,
} from "@/chamber-3d/materials/pot-pbr"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/core/scene-tokens"

export type SquarePotProps = {
  sideM: number
  heightM: number
  colors: ChamberSceneColors
  maps: PlasticPbrMaps
}

/** Injection-moulded wall thickness (meters). */
const WALL_M = 0.001

function wallBoxGeom(w: number, h: number, d: number, segs: number) {
  return <boxGeometry args={[w, h, d, segs, 1, 1]} />
}

function WallBoxes({
  halfSide,
  wallHeight,
  wallCenterY,
  wallSegs,
  materialProps,
}: {
  halfSide: number
  wallHeight: number
  wallCenterY: number
  wallSegs: number
  materialProps: Record<string, unknown>
}) {
  const side = halfSide * 2
  return (
    <group>
      {/* +Z (front) */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, halfSide]}>
        {wallBoxGeom(side, wallHeight, WALL_M, wallSegs)}
        <meshStandardMaterial {...materialProps} />
      </mesh>
      {/* -Z (back) */}
      <mesh castShadow receiveShadow position={[0, wallCenterY, -halfSide]}>
        {wallBoxGeom(side, wallHeight, WALL_M, wallSegs)}
        <meshStandardMaterial {...materialProps} />
      </mesh>
      {/* +X (right) */}
      <mesh castShadow receiveShadow position={[halfSide, wallCenterY, 0]}>
        {wallBoxGeom(WALL_M, wallHeight, side - WALL_M * 2, wallSegs)}
        <meshStandardMaterial {...materialProps} />
      </mesh>
      {/* -X (left) */}
      <mesh castShadow receiveShadow position={[-halfSide, wallCenterY, 0]}>
        {wallBoxGeom(WALL_M, wallHeight, side - WALL_M * 2, wallSegs)}
        <meshStandardMaterial {...materialProps} />
      </mesh>
    </group>
  )
}

/**
 * Square / rectangular injection-moulded PP grow pot.
 *
 * Each wall is a thin boxGeometry (1 mm thick) so there is zero z-fight
 * between inner liner and outer shell.  Soil uses the same absolute
 * tonal albedo as the felt pot.
 */
export function SquarePot({ sideM, heightM, colors, maps }: SquarePotProps) {
  const { config } = useChamberPerformance()
  const halfSide = sideM / 2
  const wallSegs = Math.max(config.potWallSegments, 24)

  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimWidth = sideM * CHAMBER_GEOMETRY.potRimRadiusExtraScale
  const rimCenterY = heightM - rimH * 0.65

  // Wall stops just below the rim.
  const wallHeight = Math.max(rimCenterY - rimH * 0.35, heightM * 0.5)
  const wallCenterY = wallHeight / 2

  // Soil recessed under the open lip.
  const soilInset = Math.max(heightM * CHAMBER_GEOMETRY.potSoilInsetScale, 0.012)
  const soilY = Math.min(rimCenterY - rimH * 0.35 - soilInset, heightM * 0.82)

  // Inner liner — inset enough to leave clear gap (no z-fight).
  const linerInset = WALL_M + 0.001
  const linerHalf = halfSide - linerInset
  const linerHeight = Math.max(soilY - 0.003, heightM * 0.35)
  const linerCenterY = linerHeight / 2

  const plasticMat = useMemo(
    () => ({
      map: maps.plastic.map,
      normalMap: maps.plastic.normalMap,
      roughnessMap: maps.plastic.roughnessMap,
      color: colors.potFelt,
      roughness: CHAMBER_MATERIAL.plasticRoughness,
      metalness: CHAMBER_MATERIAL.plasticMetalness,
      envMapIntensity: CHAMBER_MATERIAL.plasticEnvMapIntensity,
    }),
    [colors.potFelt, maps.plastic],
  )
  const rimMat = useMemo(
    () => ({
      map: maps.plastic.map,
      normalMap: maps.plastic.normalMap,
      roughnessMap: maps.plastic.roughnessMap,
      color: colors.potRim,
      roughness: CHAMBER_MATERIAL.plasticRoughness,
      metalness: CHAMBER_MATERIAL.plasticMetalness,
      envMapIntensity: CHAMBER_MATERIAL.plasticEnvMapIntensity,
    }),
    [colors.potRim, maps.plastic],
  )

  return (
    <group>
      {/* Outer walls — thin box beams (1 mm), no top/bottom face. */}
      <WallBoxes
        halfSide={halfSide}
        wallHeight={wallHeight}
        wallCenterY={wallCenterY}
        wallSegs={wallSegs}
        materialProps={plasticMat}
      />

      {/* Inner liner — separate layer, recessed from outer walls. */}
      <WallBoxes
        halfSide={linerHalf}
        wallHeight={linerHeight}
        wallCenterY={linerCenterY}
        wallSegs={wallSegs}
        materialProps={plasticMat}
      />

      {/* Bottom floor — slightly above Y=0 to avoid z-fight with growbox floor. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[sideM * 0.98, sideM * 0.98]} />
        <meshStandardMaterial {...plasticMat} />
      </mesh>

      {/* Rim — four solid box beams (injection-moulded collar). */}
      {/* Front (+Z) */}
      <mesh castShadow position={[0, rimCenterY, halfSide + rimWidth / 2]}>
        <boxGeometry args={[sideM + rimWidth * 2, rimH, rimWidth, wallSegs, 1, 1]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Back (-Z) */}
      <mesh castShadow position={[0, rimCenterY, -halfSide - rimWidth / 2]}>
        <boxGeometry args={[sideM + rimWidth * 2, rimH, rimWidth, wallSegs, 1, 1]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Right (+X) */}
      <mesh castShadow position={[halfSide + rimWidth / 2, rimCenterY, 0]}>
        <boxGeometry args={[rimWidth, rimH, sideM, 1, 1, wallSegs]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Left (-X) */}
      <mesh castShadow position={[-halfSide - rimWidth / 2, rimCenterY, 0]}>
        <boxGeometry args={[rimWidth, rimH, sideM, 1, 1, wallSegs]} />
        <meshStandardMaterial {...rimMat} />
      </mesh>

      {/* Soil surface: recessed plane, absolute-color albedo. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, soilY, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[halfSide * 2 * 0.995, halfSide * 2 * 0.995]} />
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

// -----------------------------------------------------------------------
// SquarePotGroup – same API as FeltPotGroup
// -----------------------------------------------------------------------

export type SquarePotGroupProps = {
  widthM: number
  depthM: number
  heightM: number
  preset: SquarePotPreset
  count: number
  colors: ChamberSceneColors
}

export function SquarePotGroup({
  widthM,
  depthM,
  heightM,
  preset,
  count,
  colors,
}: SquarePotGroupProps) {
  const { config } = useChamberPerformance()
  const maps = useMemo(() => createPlasticPbrMaps(config.potPbrSize), [config.potPbrSize])
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
