import { useMemo } from "react"
import { Quaternion, Vector3 } from "three"

import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

type Vec3 = readonly [number, number, number]

export type TentFrameProps = {
  widthM: number
  depthM: number
  heightM: number
  wallThicknessM: number
  radiusM: number
  colors: ChamberSceneColors
}

/**
 * Black steel tube cage: 4 uprights + top/bottom rectangles.
 * Centers sit just inside fabric lining (symmetric inset).
 */
export function TentFrame({
  widthM,
  depthM,
  heightM,
  wallThicknessM,
  radiusM,
  colors,
}: TentFrameProps) {
  const segments = useMemo(() => {
    const inset = wallThicknessM + radiusM * CHAMBER_GEOMETRY.frameInsetRadiusFactor
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
        envMapIntensity={CHAMBER_MATERIAL.frameEnvMapIntensity}
      />
    </mesh>
  )
}
