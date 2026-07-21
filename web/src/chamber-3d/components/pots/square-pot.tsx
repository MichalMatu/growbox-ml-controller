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
 * Walls are built from four PlaneGeometry panels (open box: no bottom / top
 * face) the same way the felt pot cylinder is open-ended.  A separate bottom
 * plane is placed just above Y=0 so it never z-fights the growbox floor.
 *
 * Layout (Y up, base at 0):
 *   wall:  four side planes (no bottom, no top)
 *   rim:   thin open box frame at the top opening
 *   soil:  recessed surface below the rim
 */
function wallPanelGeom(width: number, height: number, segments: number) {
  return (
    <planeGeometry args={[width, height, segments, 1]} />
  )
}

type Panel = {
  position: [number, number, number]
  rotation: [number, number, number]
  wallWidth: number
  wallHeight: number
  segments: number
}

function WallPanels({
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
  const panels: Panel[] = [
    // +Z (front)
    { position: [0, wallCenterY, halfSide], rotation: [0, 0, 0], wallWidth: side, wallHeight, segments: wallSegs },
    // -Z (back)
    { position: [0, wallCenterY, -halfSide], rotation: [0, Math.PI, 0], wallWidth: side, wallHeight, segments: wallSegs },
    // +X (right)
    { position: [halfSide, wallCenterY, 0], rotation: [0, Math.PI / 2, 0], wallWidth: side, wallHeight, segments: wallSegs },
    // -X (left)
    { position: [-halfSide, wallCenterY, 0], rotation: [0, -Math.PI / 2, 0], wallWidth: side, wallHeight, segments: wallSegs },
  ]

  return (
    <group>
      {panels.map((panel, i) => (
        <mesh
          key={i}
          castShadow
          receiveShadow
          position={panel.position}
          rotation={panel.rotation}
        >
          {wallPanelGeom(panel.wallWidth, panel.wallHeight, panel.segments)}
          <meshStandardMaterial {...materialProps} side={DoubleSide} />
        </mesh>
      ))}
    </group>
  )
}

export function SquarePot({ sideM, heightM, colors, maps }: SquarePotProps) {
  const { config } = useChamberPerformance()

  const halfSide = sideM / 2
  const rimH = Math.max(heightM * CHAMBER_GEOMETRY.potRimHeightScale, 0.008)
  const rimWidth = sideM * CHAMBER_GEOMETRY.potRimRadiusExtraScale

  // Rim sits on top of the wall.
  const rimCenterY = heightM - rimH * 0.65

  // Wall stops just below the rim so the collar sits above it.
  const wallHeight = Math.max(rimCenterY - rimH * 0.35, heightM * 0.5)
  const wallCenterY = wallHeight / 2

  // Soil recessed under the open lip.
  const soilInset = Math.max(
    heightM * CHAMBER_GEOMETRY.potSoilInsetScale,
    0.012,
  )
  const soilY = Math.min(
    rimCenterY - rimH * 0.35 - soilInset,
    heightM * 0.82,
  )

  // Inner liner — inset enough to avoid z-fight with outer walls.
  const linerInset = Math.max(sideM * 0.03, 0.006)
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
      {/* Outer walls — four side panels, no bottom face, no top face. */}
      <WallPanels
        halfSide={halfSide}
        wallHeight={wallHeight}
        wallCenterY={wallCenterY}
        wallSegs={wallSegs}
        materialProps={plasticMat}
      />

      {/* Inner liner below soil — four side panels, no bottom face. */}
      <WallPanels
        halfSide={linerHalf}
        wallHeight={linerHeight}
        wallCenterY={linerCenterY}
        wallSegs={wallSegs}
        materialProps={plasticMat}
      />

      {/* Bottom floor — slightly above Y=0, avoids z-fight with growbox floor. */}
      <mesh
        castShadow
        receiveShadow
        position={[0, 0.001, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[sideM * 0.98, sideM * 0.98]} />
        <meshStandardMaterial {...plasticMat} />
      </mesh>

      {/* Rim — four thin box beams forming a solid lip / collar.
          Each beam has full thickness (rimWidth) so the rim reads as a
          thick injection-moulded collar, not a flat transparent panel. */}
      {/* Front (+Z) */}
      <mesh castShadow position={[0, rimCenterY, halfSide + rimWidth / 2]}>
        <boxGeometry
          args={[sideM + rimWidth * 2, rimH, rimWidth, wallSegs, 1, 1]}
        />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Back (-Z) */}
      <mesh castShadow position={[0, rimCenterY, -halfSide - rimWidth / 2]}>
        <boxGeometry
          args={[sideM + rimWidth * 2, rimH, rimWidth, wallSegs, 1, 1]}
        />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Right (+X) */}
      <mesh castShadow position={[halfSide + rimWidth / 2, rimCenterY, 0]}>
        <boxGeometry
          args={[rimWidth, rimH, sideM, 1, 1, wallSegs]}
        />
        <meshStandardMaterial {...rimMat} />
      </mesh>
      {/* Left (-X) */}
      <mesh castShadow position={[-halfSide - rimWidth / 2, rimCenterY, 0]}>
        <boxGeometry
          args={[rimWidth, rimH, sideM, 1, 1, wallSegs]}
        />
        <meshStandardMaterial {...rimMat} />
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
