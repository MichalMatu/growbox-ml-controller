import { useEffect, useMemo } from "react"
import { BoxGeometry, MeshStandardMaterial, Vector2 } from "three"

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

/**
 * Solid fabric slab. Dual planes left an open edge gap where the silver
 * interior foil read as a white triangle / canopy at corners.
 * Box faces: +Z exterior nylon, -Z interior foil, rim faces matte exterior.
 */
function makeFabricBoxGeometry(
  width: number,
  height: number,
  thickness: number,
  repeatU: number,
  repeatV: number,
): BoxGeometry {
  const geometry = new BoxGeometry(width, height, thickness)
  const uv = geometry.getAttribute("uv")
  if (uv) {
    // BoxGeometry face order: +X, -X, +Y, -Y, +Z, -Z (4 verts each).
    // Tile the large faces (+Z exterior, -Z interior). Rim faces stay 0–1.
    for (const face of [4, 5]) {
      const base = face * 4
      for (let i = 0; i < 4; i += 1) {
        const idx = base + i
        uv.setXY(idx, uv.getX(idx) * repeatU, uv.getY(idx) * repeatV)
      }
    }
    uv.needsUpdate = true
    geometry.setAttribute("uv2", uv.clone())
  }
  return geometry
}

/**
 * Solid dual-sided fabric wall. Local +Z = exterior (nylon), local -Z = interior (foil).
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
  const sizeW = size[0]
  const sizeH = size[1]
  const uvU = uvScale[0]
  const uvV = uvScale[1]

  const geometry = useMemo(
    () => makeFabricBoxGeometry(sizeW, sizeH, thicknessM, uvU, uvV),
    [sizeW, sizeH, thicknessM, uvU, uvV],
  )

  const faceMaterials = useMemo(() => {
    const rim = new MeshStandardMaterial({
      color: colors.exterior,
      roughness: CHAMBER_MATERIAL.exteriorRoughness,
      metalness: CHAMBER_MATERIAL.exteriorMetalness,
      envMapIntensity: CHAMBER_MATERIAL.exteriorEnvMapIntensity,
    })
    const exterior = new MeshStandardMaterial({
      color: colors.exterior,
      map: exteriorMaps.map,
      normalMap: exteriorMaps.normalMap,
      normalScale: EXTERIOR_NORMAL_SCALE,
      roughnessMap: exteriorMaps.roughnessMap,
      metalness: CHAMBER_MATERIAL.exteriorMetalness,
      aoMap: exteriorMaps.aoMap,
      aoMapIntensity: CHAMBER_MATERIAL.exteriorAoIntensity,
      roughness: CHAMBER_MATERIAL.exteriorRoughness,
      envMapIntensity: CHAMBER_MATERIAL.exteriorEnvMapIntensity,
    })
    const interior = new MeshStandardMaterial({
      color: colors.interior,
      map: interiorMaps.map,
      normalMap: interiorMaps.normalMap,
      normalScale: INTERIOR_NORMAL_SCALE,
      roughnessMap: interiorMaps.roughnessMap,
      metalnessMap: interiorMaps.metalnessMap,
      aoMap: interiorMaps.aoMap,
      aoMapIntensity: CHAMBER_MATERIAL.interiorAoIntensity,
      roughness: CHAMBER_MATERIAL.interiorRoughness,
      metalness: CHAMBER_MATERIAL.interiorMetalness,
      envMapIntensity: CHAMBER_MATERIAL.interiorEnvMapIntensity,
    })
    // Box face order: +X, -X, +Y, -Y, +Z, -Z
    return [rim, rim, rim, rim, exterior, interior]
  }, [colors.exterior, colors.interior, exteriorMaps, interiorMaps])

  useEffect(() => {
    return () => {
      geometry.dispose()
    }
  }, [geometry])

  useEffect(() => {
    return () => {
      const seen = new Set<MeshStandardMaterial>()
      for (const mat of faceMaterials) {
        if (!seen.has(mat)) {
          seen.add(mat)
          mat.dispose()
        }
      }
    }
  }, [faceMaterials])

  return (
    <group position={position} rotation={rotation}>
      <mesh
        geometry={geometry}
        material={faceMaterials}
        castShadow
        receiveShadow
      />
    </group>
  )
}
