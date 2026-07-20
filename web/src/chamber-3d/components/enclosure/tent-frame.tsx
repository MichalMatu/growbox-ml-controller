import { useEffect, useMemo } from "react"
import { MeshStandardMaterial } from "three"

import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { orientSegmentBetween } from "@/chamber-3d/utils/segment-mesh"
import {
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/core/scene-tokens"
import {
  buildFrameCorners,
  buildFrameSegments,
  computeFrameCornerBox,
  type Vec3,
} from "@/chamber-3d/components/enclosure/tent-frame-geometry"

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
 *
 * Uses a SINGLE shared MeshStandardMaterial for all frame elements
 * (was 20 separate material instances — ~0 value for draw calls / GPU memory).
 */
export function TentFrame({
  widthM,
  depthM,
  heightM,
  radiusM,
  colors,
}: TentFrameProps) {
  const { config } = useChamberPerformance()
  const segs = config.frameRadialSegments

  const box = useMemo(
    () => computeFrameCornerBox(widthM, depthM, heightM, radiusM),
    [widthM, depthM, heightM, radiusM],
  )
  const segments = useMemo(() => buildFrameSegments(box), [box])
  const corners = useMemo(() => buildFrameCorners(box), [box])

  // Shared frame material — one instance for all tubes + corners.
  const sharedMaterial = useMemo(() => {
    return new MeshStandardMaterial({
      color: colors.frame,
      roughness: CHAMBER_MATERIAL.frameRoughness,
      metalness: CHAMBER_MATERIAL.frameMetalness,
      envMapIntensity: CHAMBER_MATERIAL.frameEnvMapIntensity,
    })
  }, [colors.frame])

  useEffect(() => {
    return () => sharedMaterial.dispose()
  }, [sharedMaterial])

  return (
    <group>
      {segments.map(([from, to], index) => (
        <FrameTube
          key={`tube-${index}`}
          from={from}
          to={to}
          radiusM={radiusM}
          radialSegments={segs}
          material={sharedMaterial}
        />
      ))}
      {corners.map((corner, index) => (
        <mesh
          key={`corner-${index}`}
          position={corner}
          castShadow
          receiveShadow
          material={sharedMaterial}
        >
          <sphereGeometry args={[radiusM, segs, segs]} />
        </mesh>
      ))}
    </group>
  )
}

function FrameTube({
  from,
  to,
  radiusM,
  radialSegments,
  material,
}: {
  from: Vec3
  to: Vec3
  radiusM: number
  radialSegments: number
  material: MeshStandardMaterial
}) {
  const { position, quaternion, length } = useMemo(
    () => orientSegmentBetween(from, to),
    [from, to],
  )

  if (length < 1e-6) return null

  return (
    <mesh
      position={position}
      quaternion={quaternion}
      castShadow
      receiveShadow
      material={material}
    >
      <cylinderGeometry args={[radiusM, radiusM, length, radialSegments]} />
    </mesh>
  )
}
