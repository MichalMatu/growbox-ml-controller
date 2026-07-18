import { useMemo } from "react"
import { Quaternion, Vector3 } from "three"

import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"
import {
  buildFrameSegments,
  computeFrameCornerBox,
  type Vec3,
} from "@/chamber-3d/tent-frame-geometry"

export type TentFrameProps = {
  widthM: number
  depthM: number
  heightM: number
  radiusM: number
  colors: ChamberSceneColors
}

/**
 * Black steel tube cage (R3F). Geometry: `tent-frame-geometry.ts`.
 * Outer-pocket inset on all axes; axis-aligned edges → 90° joints.
 */
export function TentFrame({
  widthM,
  depthM,
  heightM,
  radiusM,
  colors,
}: TentFrameProps) {
  const segments = useMemo(
    () =>
      buildFrameSegments(
        computeFrameCornerBox(widthM, depthM, heightM, radiusM),
      ),
    [widthM, depthM, heightM, radiusM],
  )

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
