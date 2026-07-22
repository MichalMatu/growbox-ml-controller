import { useMemo } from "react"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"

/**
 * Inline duct fan 3D mesh.
 * Local space: length +X, vertical +Y, width +Z.
 *
 * Shape (left → right along X):
 *   spigot-left → cone-left → body-cylinder → cone-right → spigot-right
 *
 * All cylinders are oriented along X (rotation Z = PI/2).
 */
export function InlineFanMesh({
  bodyDiameterM,
  bodyLengthM,
  ductDiameterM,
  ductLengthM,
  coneLengthM,
  colors,
}: {
  bodyDiameterM: number
  bodyLengthM: number
  ductDiameterM: number
  ductLengthM: number
  coneLengthM: number
  colors: ChamberSceneColors
}) {
  const bodyR = bodyDiameterM / 2
  const ductR = ductDiameterM / 2

  const segments = 28

  const housingMat = useMemo(
    () => ({
      color: colors.fanHousing,
      roughness: CHAMBER_MATERIAL.fanHousingRoughness,
      metalness: CHAMBER_MATERIAL.fanHousingMetalness,
      envMapIntensity: CHAMBER_MATERIAL.fanHousingEnvMapIntensity,
    }),
    [colors.fanHousing],
  )

  const ductMat = useMemo(
    () => ({
      color: colors.fanDuct,
      roughness: CHAMBER_MATERIAL.fanDuctRoughness,
      metalness: CHAMBER_MATERIAL.fanDuctMetalness,
      envMapIntensity: CHAMBER_MATERIAL.fanDuctEnvMapIntensity,
    }),
    [colors.fanDuct],
  )

  // Positions along X axis, from left (negative X) to right (positive X)
  const halfBody = bodyLengthM / 2
  const coneStartLeft = -halfBody
  const ductStartLeft = coneStartLeft - coneLengthM
  const coneStartRight = halfBody
  const ductStartRight = coneStartRight + coneLengthM

  // Center X for each piece
  const bodyCenterX = 0
  const coneLeftCenterX = coneStartLeft - coneLengthM / 2
  const coneRightCenterX = coneStartRight + coneLengthM / 2
  const ductLeftCenterX = ductStartLeft - ductLengthM / 2
  const ductRightCenterX = ductStartRight + ductLengthM / 2

  return (
    <group rotation={[0, Math.PI / 2, 0]}>
      {/* Motor body cylinder */}
      <mesh
        position={[bodyCenterX, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
        receiveShadow
      >
        <cylinderGeometry args={[bodyR, bodyR, bodyLengthM, segments]} />
        <meshStandardMaterial {...housingMat} />
      </mesh>

      {/* Left reducer cone: bodyR (at body, -X local → +X scene) → ductR (at spigot, +X local → -X scene)
          After rotation Z=PI/2: radiusTop → scene -X (spigot), radiusBottom → scene +X (body). */}
      <mesh
        position={[coneLeftCenterX, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry
          args={[ductR, bodyR, coneLengthM, segments, 1]}
        />
        <meshStandardMaterial {...ductMat} />
      </mesh>

      {/* Right reducer cone: bodyR (at body, +X local → -X scene) → ductR (at spigot, -X local → +X scene)
          After rotation Z=PI/2: radiusTop → scene -X (body), radiusBottom → scene +X (spigot). */}
      <mesh
        position={[coneRightCenterX, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry
          args={[bodyR, ductR, coneLengthM, segments, 1]}
        />
        <meshStandardMaterial {...ductMat} />
      </mesh>

      {/* Left spigot cylinder */}
      <mesh
        position={[ductLeftCenterX, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[ductR, ductR, ductLengthM, segments]} />
        <meshStandardMaterial {...ductMat} />
      </mesh>

      {/* Right spigot cylinder */}
      <mesh
        position={[ductRightCenterX, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[ductR, ductR, ductLengthM, segments]} />
        <meshStandardMaterial {...ductMat} />
      </mesh>

      {/* Decorative ring ridges on body */}
      <RingRidge
        offsetX={-bodyLengthM * 0.3}
        radius={bodyR + 0.002}
        ringLengthM={0.003}
        colors={colors}
      />
      <RingRidge
        offsetX={bodyLengthM * 0.3}
        radius={bodyR + 0.002}
        ringLengthM={0.003}
        colors={colors}
      />
    </group>
  )
}

/** Thin raised ring around the motor body (decorative stamping). */
function RingRidge({
  offsetX,
  radius,
  ringLengthM,
  colors,
}: {
  offsetX: number
  radius: number
  ringLengthM: number
  colors: ChamberSceneColors
}) {
  return (
    <mesh
      position={[offsetX, 0, 0]}
      rotation={[0, 0, Math.PI / 2]}
      castShadow
    >
      <cylinderGeometry args={[radius, radius, ringLengthM, 32, 1, true]} />
      <meshStandardMaterial
        color={colors.fanHousing}
        roughness={CHAMBER_MATERIAL.fanHousingRoughness * 0.8}
        metalness={CHAMBER_MATERIAL.fanHousingMetalness}
        envMapIntensity={CHAMBER_MATERIAL.fanHousingEnvMapIntensity}
      />
    </mesh>
  )
}
