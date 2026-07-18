import { useEffect, useMemo } from "react"
import { PlaneGeometry, Vector2 } from "three"

import {
  useGrowtentPbrMaps,
  type ExteriorPbrMaps,
  type GrowtentPbrMaps,
  type InteriorPbrMaps,
} from "@/chamber-3d/fabric-pbr"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"
import { TentFrame } from "@/chamber-3d/tent-frame"

export type EnclosureDimensions = {
  widthCm: number
  depthCm: number
  heightCm: number
  colors: ChamberSceneColors
}

type Vec3 = readonly [number, number, number]

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
  const widthM = Math.max(widthCm, 1) / 100
  const depthM = Math.max(depthCm, 1) / 100
  const heightM = Math.max(heightCm, 1) / 100
  const t = CHAMBER_GEOMETRY.wallThicknessM
  const r = CHAMBER_GEOMETRY.frameRadiusM
  const halfW = widthM / 2
  const halfD = depthM / 2
  const pbr = useGrowtentPbrMaps()

  return (
    <group>
      <TentShell
        widthM={widthM}
        depthM={depthM}
        heightM={heightM}
        thicknessM={t}
        halfW={halfW}
        halfD={halfD}
        colors={colors}
        pbr={pbr}
      />
      <TentFrame
        widthM={widthM}
        depthM={depthM}
        heightM={heightM}
        wallThicknessM={t}
        radiusM={r}
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
  halfW,
  halfD,
  colors,
  pbr,
}: {
  widthM: number
  depthM: number
  heightM: number
  thicknessM: number
  halfW: number
  halfD: number
  colors: ChamberSceneColors
  pbr: GrowtentPbrMaps
}) {
  const t = thicknessM
  const uv = CHAMBER_GEOMETRY.uvTilesPerMeter

  const panels: Array<{
    size: [number, number]
    position: Vec3
    rotation: Vec3
    uvScale: [number, number]
  }> = [
    {
      size: [widthM, depthM],
      position: [0, t / 2, 0],
      rotation: [Math.PI / 2, 0, 0],
      uvScale: [widthM * uv, depthM * uv],
    },
    {
      size: [widthM, depthM],
      position: [0, heightM - t / 2, 0],
      rotation: [-Math.PI / 2, 0, 0],
      uvScale: [widthM * uv, depthM * uv],
    },
    {
      size: [widthM, heightM],
      position: [0, heightM / 2, -halfD + t / 2],
      rotation: [0, Math.PI, 0],
      uvScale: [widthM * uv, heightM * uv],
    },
    {
      size: [depthM, heightM],
      position: [-halfW + t / 2, heightM / 2, 0],
      rotation: [0, -Math.PI / 2, 0],
      uvScale: [depthM * uv, heightM * uv],
    },
    {
      size: [depthM, heightM],
      position: [halfW - t / 2, heightM / 2, 0],
      rotation: [0, Math.PI / 2, 0],
      uvScale: [depthM * uv, heightM * uv],
    },
  ]

  return (
    <group>
      {panels.map((panel, index) => (
        <FabricPanel
          key={index}
          size={panel.size}
          position={panel.position}
          rotation={panel.rotation}
          thicknessM={t}
          colors={colors}
          exteriorMaps={pbr.exterior}
          interiorMaps={pbr.interior}
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
  size: [number, number]
  position: Vec3
  rotation: Vec3
  thicknessM: number
  colors: ChamberSceneColors
  exteriorMaps: ExteriorPbrMaps
  interiorMaps: InteriorPbrMaps
  uvScale: [number, number]
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

  const exteriorNormalScale = useMemo(
    () =>
      new Vector2(
        CHAMBER_MATERIAL.exteriorNormalScale,
        CHAMBER_MATERIAL.exteriorNormalScale,
      ),
    [],
  )
  const interiorNormalScale = useMemo(
    () =>
      new Vector2(
        CHAMBER_MATERIAL.interiorNormalScale,
        CHAMBER_MATERIAL.interiorNormalScale,
      ),
    [],
  )

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
          normalScale={exteriorNormalScale}
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
          normalScale={interiorNormalScale}
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
