import { useMemo } from "react"

import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { orientSegmentBetween } from "@/chamber-3d/utils/segment-mesh"
import { type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
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
 * Uses R3F declarative JSX material (meshStandardMaterial child) so React
 * owns all prop updates — no useMemo/useLayoutEffect timing issues.
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

  return (
    <group>
      {segments.map(([from, to], index) => (
        <FrameTube
          key={`tube-${index}`}
          from={from}
          to={to}
          radiusM={radiusM}
          radialSegments={segs}
          color={colors.frame}
        />
      ))}
      {corners.map((corner, index) => (
        <mesh
          key={`corner-${index}`}
          position={corner}
          castShadow
          receiveShadow
        >
          <sphereGeometry args={[radiusM, segs, segs]} />
          <meshLambertMaterial color={colors.frame} />
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
  color,
}: {
  from: Vec3
  to: Vec3
  radiusM: number
  radialSegments: number
  color: string
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
    >
      <cylinderGeometry args={[radiusM, radiusM, length, radialSegments]} />
      <meshLambertMaterial color={color} />
    </mesh>
  )
}
