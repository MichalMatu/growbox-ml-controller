import { useEffect, useMemo } from "react"
import { PlaneGeometry, Vector2 } from "three"

import {
  useGrowtentPbrMaps,
  type ExteriorPbrMaps,
  type InteriorPbrMaps,
} from "@/chamber-3d/fabric-pbr"
import { ENCLOSURE_CM_MIN } from "@/chamber-3d/enclosure-cm"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"
import { TentFrame } from "@/chamber-3d/tent-frame"
import type { Vec3 } from "@/chamber-3d/tent-frame-geometry"
import { buildShellPanels } from "@/chamber-3d/tent-shell-geometry"

export type EnclosureDimensions = {
  widthCm: number
  depthCm: number
  heightCm: number
  colors: ChamberSceneColors
}

/** Module-level normal scales (shared; not recreated per panel). */
const EXTERIOR_NORMAL_SCALE = new Vector2(
  CHAMBER_MATERIAL.exteriorNormalScale,
  CHAMBER_MATERIAL.exteriorNormalScale,
)
const INTERIOR_NORMAL_SCALE = new Vector2(
  CHAMBER_MATERIAL.interiorNormalScale,
  CHAMBER_MATERIAL.interiorNormalScale,
)

/**
 * Parametric grow tent: open front (+Z), dual-sided fabric
 * (FreePBR nylon exterior + ambientCG Foil003 interior), black steel frame.
 */
export function Enclosure({
  widthCm,
  depthCm,
  heightCm,
  colors,
}: EnclosureDimensions) {
  // UI enforces min cm; floor here so bad props never collapse the mesh.
  const widthM = Math.max(widthCm, ENCLOSURE_CM_MIN) / 100
  const depthM = Math.max(depthCm, ENCLOSURE_CM_MIN) / 100
  const heightM = Math.max(heightCm, ENCLOSURE_CM_MIN) / 100
  const thicknessM = CHAMBER_GEOMETRY.wallThicknessM
  const radiusM = CHAMBER_GEOMETRY.frameRadiusM
  const pbr = useGrowtentPbrMaps()

  return (
    <group>
      <TentShell
        widthM={widthM}
        depthM={depthM}
        heightM={heightM}
        thicknessM={thicknessM}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
      />
      <TentFrame
        widthM={widthM}
        depthM={depthM}
        heightM={heightM}
        radiusM={radiusM}
        colors={colors}
      />
    </group>
  )
}

function TentShell({
  widthM,
  depthM,
  heightM,
  thicknessM,
  colors,
  exteriorMaps,
  interiorMaps,
}: {
  widthM: number
  depthM: number
  heightM: number
  thicknessM: number
  colors: ChamberSceneColors
  exteriorMaps: ExteriorPbrMaps
  interiorMaps: InteriorPbrMaps
}) {
  const panels = useMemo(
    () => buildShellPanels(widthM, depthM, heightM, thicknessM),
    [widthM, depthM, heightM, thicknessM],
  )

  return (
    <group>
      {panels.map((panel, index) => (
        <FabricPanel
          key={index}
          size={panel.size}
          position={panel.position}
          rotation={panel.rotation}
          thicknessM={thicknessM}
          colors={colors}
          exteriorMaps={exteriorMaps}
          interiorMaps={interiorMaps}
          uvScale={panel.uvScale}
        />
      ))}
    </group>
  )
}

/** Plane with tiled UVs + uv2 for aoMap (shared maps; no per-panel texture clones). */
function makeTiledPlane(
  width: number,
  height: number,
  repeatU: number,
  repeatV: number,
): PlaneGeometry {
  const geometry = new PlaneGeometry(width, height)
  const uv = geometry.getAttribute("uv")
  if (uv) {
    for (let i = 0; i < uv.count; i += 1) {
      uv.setXY(i, uv.getX(i) * repeatU, uv.getY(i) * repeatV)
    }
    uv.needsUpdate = true
    geometry.setAttribute("uv2", uv.clone())
  }
  return geometry
}

/**
 * Dual-plane fabric wall. Local +Z = exterior (nylon), local -Z = interior (foil).
 */
function FabricPanel({
  size,
  position,
  rotation,
  thicknessM,
  colors,
  exteriorMaps,
  interiorMaps,
  uvScale,
}: {
  size: readonly [number, number]
  position: Vec3
  rotation: Vec3
  thicknessM: number
  colors: ChamberSceneColors
  exteriorMaps: ExteriorPbrMaps
  interiorMaps: InteriorPbrMaps
  uvScale: readonly [number, number]
}) {
  const halfT = thicknessM / 2
  const sizeW = size[0]
  const sizeH = size[1]
  const uvU = uvScale[0]
  const uvV = uvScale[1]

  const geometry = useMemo(
    () => makeTiledPlane(sizeW, sizeH, uvU, uvV),
    [sizeW, sizeH, uvU, uvV],
  )

  useEffect(() => {
    return () => {
      geometry.dispose()
    }
  }, [geometry])

  return (
    <group position={position} rotation={rotation}>
      <mesh
        geometry={geometry}
        position={[0, 0, halfT]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          color={colors.exterior}
          map={exteriorMaps.map}
          normalMap={exteriorMaps.normalMap}
          normalScale={EXTERIOR_NORMAL_SCALE}
          roughnessMap={exteriorMaps.roughnessMap}
          metalness={CHAMBER_MATERIAL.exteriorMetalness}
          aoMap={exteriorMaps.aoMap}
          aoMapIntensity={CHAMBER_MATERIAL.exteriorAoIntensity}
          roughness={CHAMBER_MATERIAL.exteriorRoughness}
          envMapIntensity={CHAMBER_MATERIAL.exteriorEnvMapIntensity}
        />
      </mesh>
      <mesh
        geometry={geometry}
        position={[0, 0, -halfT]}
        rotation={[0, Math.PI, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          color={colors.interior}
          map={interiorMaps.map}
          normalMap={interiorMaps.normalMap}
          normalScale={INTERIOR_NORMAL_SCALE}
          roughnessMap={interiorMaps.roughnessMap}
          metalnessMap={interiorMaps.metalnessMap}
          aoMap={interiorMaps.aoMap}
          aoMapIntensity={CHAMBER_MATERIAL.interiorAoIntensity}
          roughness={CHAMBER_MATERIAL.interiorRoughness}
          metalness={CHAMBER_MATERIAL.interiorMetalness}
          envMapIntensity={CHAMBER_MATERIAL.interiorEnvMapIntensity}
        />
      </mesh>
    </group>
  )
}
