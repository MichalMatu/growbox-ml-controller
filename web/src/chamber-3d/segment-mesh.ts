import { Quaternion, Vector3 } from "three"

import type { Vec3 } from "@/chamber-3d/tent-frame-geometry"

const UP = new Vector3(0, 1, 0)

export type OrientedSegment = {
  readonly position: Vec3
  readonly quaternion: Quaternion
  readonly length: number
}

/**
 * Place a Y-up cylinder (or similar) between two points in local/world space.
 * Shared by frame tubes and zipper coils.
 */
export function orientSegmentBetween(from: Vec3, to: Vec3): OrientedSegment {
  const start = new Vector3(from[0], from[1], from[2])
  const end = new Vector3(to[0], to[1], to[2])
  const dir = end.clone().sub(start)
  const length = dir.length()
  const mid = start.clone().add(end).multiplyScalar(0.5)
  const quaternion = new Quaternion()
  if (length > 1e-8) {
    quaternion.setFromUnitVectors(UP, dir.normalize())
  }
  return {
    position: [mid.x, mid.y, mid.z],
    quaternion,
    length,
  }
}
