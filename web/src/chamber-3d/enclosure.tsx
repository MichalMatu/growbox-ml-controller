import { useEffect, useMemo } from "react"
import { PlaneGeometry, Quaternion, Vector2, Vector3 } from "three"

import {
  useGrowtentPbrMaps,
  type GrowtentPbrMaps,
  type PbrMapBundle,
} from "@/chamber-3d/fabric-pbr"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

export type EnclosureDimensions = {
  widthCm: number
  depthCm: number
  heightCm: number
  colors: ChamberSceneColors
}

type Vec3 = readonly [number, number, number]

/**
 * Parametric grow tent: open front (+Z), dual-sided PBR fabric
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
  // ~1 texture tile per 45 cm of wall (baked into geometry UVs)
  const uvPerMeter = 100 / 45

  return (
    <group>
      <FabricPanel
        size={[widthM, depthM]}
        position={[0, t / 2, 0]}
        rotation={[Math.PI / 2, 0, 0]}
        thicknessM={t}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
        uvScale={[widthM * uvPerMeter, depthM * uvPerMeter]}
      />
      <FabricPanel
        size={[widthM, depthM]}
        position={[0, heightM - t / 2, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        thicknessM={t}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
        uvScale={[widthM * uvPerMeter, depthM * uvPerMeter]}
      />
      <FabricPanel
        size={[widthM, heightM]}
        position={[0, heightM / 2, -halfD + t / 2]}
        rotation={[0, Math.PI, 0]}
        thicknessM={t}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
        uvScale={[widthM * uvPerMeter, heightM * uvPerMeter]}
      />
      <FabricPanel
        size={[depthM, heightM]}
        position={[-halfW + t / 2, heightM / 2, 0]}
        rotation={[0, -Math.PI / 2, 0]}
        thicknessM={t}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
        uvScale={[depthM * uvPerMeter, heightM * uvPerMeter]}
      />
      <FabricPanel
        size={[depthM, heightM]}
        position={[halfW - t / 2, heightM / 2, 0]}
        rotation={[0, Math.PI / 2, 0]}
        thicknessM={t}
        colors={colors}
        exteriorMaps={pbr.exterior}
        interiorMaps={pbr.interior}
        uvScale={[depthM * uvPerMeter, heightM * uvPerMeter]}
      />
    </group>
  )
}

/** Plane with tiled UVs + uv2 for aoMap (no per-panel texture clones). */
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
 * Shared PBR maps; tiling is in geometry UVs.
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
  exteriorMaps: PbrMapBundle
  interiorMaps: PbrMapBundle
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
          metalnessMap={exteriorMaps.metalnessMap}
          aoMap={exteriorMaps.aoMap}
          aoMapIntensity={CHAMBER_MATERIAL.exteriorAoIntensity}
          roughness={CHAMBER_MATERIAL.exteriorRoughness}
          metalness={CHAMBER_MATERIAL.exteriorMetalness}
          envMapIntensity={0.35}
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
          // white: foil albedo is full PBR color (token tint would muddy metal)
          color="white"
          map={interiorMaps.map}
          normalMap={interiorMaps.normalMap}
          normalScale={interiorNormalScale}
          roughnessMap={interiorMaps.roughnessMap}
          metalnessMap={interiorMaps.metalnessMap}
          aoMap={interiorMaps.aoMap}
          aoMapIntensity={CHAMBER_MATERIAL.interiorAoIntensity}
          roughness={CHAMBER_MATERIAL.interiorRoughness}
          metalness={CHAMBER_MATERIAL.interiorMetalness}
          envMapIntensity={1.8}
        />
      </mesh>
    </group>
  )
}

function TentFrame({
  widthM,
  depthM,
  heightM,
  wallThicknessM,
  radiusM,
  colors,
}: {
  widthM: number
  depthM: number
  heightM: number
  wallThicknessM: number
  radiusM: number
  colors: ChamberSceneColors
}) {
  const segments = useMemo(() => {
    const inset = wallThicknessM + radiusM * 1.05
    const halfW = widthM / 2 - inset
    const halfD = depthM / 2 - inset
    const yBottom = wallThicknessM + radiusM
    const yTop = heightM - wallThicknessM - radiusM

    const bl: Vec3 = [-halfW, yBottom, -halfD]
    const br: Vec3 = [halfW, yBottom, -halfD]
    const fl: Vec3 = [-halfW, yBottom, halfD]
    const fr: Vec3 = [halfW, yBottom, halfD]
    const tl: Vec3 = [-halfW, yTop, -halfD]
    const tr: Vec3 = [halfW, yTop, -halfD]
    const tfl: Vec3 = [-halfW, yTop, halfD]
    const tfr: Vec3 = [halfW, yTop, halfD]

    return [
      [bl, tl],
      [br, tr],
      [fl, tfl],
      [fr, tfr],
      [bl, br],
      [br, fr],
      [fr, fl],
      [fl, bl],
      [tl, tr],
      [tr, tfr],
      [tfr, tfl],
      [tfl, tl],
    ] as const satisfies ReadonlyArray<readonly [Vec3, Vec3]>
  }, [widthM, depthM, heightM, wallThicknessM, radiusM])

  return (
    <group>
      {segments.map(([from, to], index) => (
        <FrameTube
          key={index}
          from={from}
          to={to}
          radiusM={radiusM}
          colors={colors}
        />
      ))}
    </group>
  )
}

const UP = new Vector3(0, 1, 0)

function FrameTube({
  from,
  to,
  radiusM,
  colors,
}: {
  from: Vec3
  to: Vec3
  radiusM: number
  colors: ChamberSceneColors
}) {
  const { position, quaternion, length } = useMemo(() => {
    const start = new Vector3(from[0], from[1], from[2])
    const end = new Vector3(to[0], to[1], to[2])
    const dir = end.clone().sub(start)
    const lengthM = dir.length()
    const mid = start.clone().add(end).multiplyScalar(0.5)
    const quat = new Quaternion()
    if (lengthM > 1e-8) {
      quat.setFromUnitVectors(UP, dir.normalize())
    }
    return {
      position: [mid.x, mid.y, mid.z] as Vec3,
      quaternion: quat,
      length: lengthM,
    }
  }, [from, to])

  if (length < 1e-6) return null

  return (
    <mesh position={position} quaternion={quaternion} castShadow receiveShadow>
      <cylinderGeometry
        args={[
          radiusM,
          radiusM,
          length,
          CHAMBER_GEOMETRY.frameRadialSegments,
        ]}
      />
      <meshStandardMaterial
        color={colors.frame}
        roughness={CHAMBER_MATERIAL.frameRoughness}
        metalness={CHAMBER_MATERIAL.frameMetalness}
        envMapIntensity={0.6}
      />
    </mesh>
  )
}
