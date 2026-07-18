import { useMemo } from "react"

import { orientSegmentBetween } from "@/chamber-3d/segment-mesh"
import {
  CHAMBER_GEOMETRY,
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/scene-tokens"
import {
  buildFrameCorners,
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
 * Corner spheres fill the gap where three cylinder ends would leave a hole.
 */
export function TentFrame({
  widthM,
  depthM,
  heightM,
  radiusM,
  colors,
}: TentFrameProps) {
  const box = useMemo(
    () => computeFrameCornerBox(widthM, depthM, heightM, radiusM),
    [widthM, depthM, heightM, radiusM],
  )
  const segments = useMemo(() => buildFrameSegments(box), [box])
  const corners = useMemo(() => buildFrameCorners(box), [box])

  return (
    <group>
      {segments.map(([from, to], index) => (
        <FrameTube
          key={`tube-${index}`}
          from={from}
          to={to}
          radiusM={radiusM}
          colors={colors}
        />
      ))}
      {corners.map((corner, index) => (
        <mesh
          key={`corner-${index}`}
          position={corner}
          castShadow
          receiveShadow
        >
          <sphereGeometry
            args={[
              radiusM,
              CHAMBER_GEOMETRY.frameRadialSegments,
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
      ))}
    </group>
  )
}

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
  const { position, quaternion, length } = useMemo(
    () => orientSegmentBetween(from, to),
    [from, to],
  )

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
