import { useLayoutEffect, useMemo, useRef } from "react"
import { Object3D, type InstancedMesh } from "three"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"
import { sceneIntensity, useLightMaterials } from "./light-materials"

const _diodeDummy = new Object3D()

export function LedPanelMesh({
  lengthM,
  widthM,
  heightM,
  colors,
  lit,
  fixtureShadows,
  powerScale,
}: {
  lengthM: number
  widthM: number
  heightM: number
  colors: ChamberSceneColors
  lit: boolean
  fixtureShadows: boolean
  powerScale: number
}) {
  const castSpotShadow = lit && fixtureShadows
  const mats = useLightMaterials(colors, lit)
  const bodyH = heightM * 0.72
  const plateH = heightM * 0.18
  const topY = heightM / 2
  const housingCenterY = topY - bodyH / 2
  const plateCenterY = housingCenterY - bodyH / 2 - plateH / 2 - 0.001
  const diodeY = plateCenterY - plateH / 2 - 0.002

  const diodeGrid = useMemo(() => {
    const pitch = CHAMBER_MATERIAL.ledDiodePitchM
    const maxAxis = CHAMBER_MATERIAL.ledDiodeMaxAxis
    const usableL = lengthM * 0.9
    const usableW = widthM * 0.9
    const cols = Math.min(
      maxAxis,
      Math.max(4, Math.floor(usableL / pitch)),
    )
    const rows = Math.min(
      maxAxis,
      Math.max(3, Math.floor(usableW / pitch)),
    )
    const spanX = (cols - 1) * pitch
    const spanZ = (rows - 1) * pitch
    const originX = -spanX / 2
    const originZ = -spanZ / 2
    const radius =
      pitch * CHAMBER_MATERIAL.ledDiodeRadiusScale * 0.5
    const positions: { x: number; z: number }[] = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        positions.push({
          x: originX + c * pitch,
          z: originZ + r * pitch,
        })
      }
    }
    return { cols, rows, positions, radius, pitch }
  }, [lengthM, widthM])

  const diodeMeshRef = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const mesh = diodeMeshRef.current
    if (!mesh) return
    const { positions } = diodeGrid
    for (let i = 0; i < positions.length; i++) {
      const p = positions[i]!
      _diodeDummy.position.set(p.x, 0, p.z)
      _diodeDummy.scale.set(1, 1, 1)
      _diodeDummy.updateMatrix()
      mesh.setMatrixAt(i, _diodeDummy.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
    mesh.count = positions.length
  }, [diodeGrid])

  const fillI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.ledPanelFillIntensity,
    powerScale,
  )
  const spotI = sceneIntensity(
    lit,
    CHAMBER_MATERIAL.ledPanelSpotIntensity,
    powerScale,
  )
  const lightY = diodeY - 0.02
  const sceneColor = colors.lightLedScene

  return (
    <group>
      <mesh position={[0, housingCenterY, 0]} castShadow receiveShadow>
        <boxGeometry args={[lengthM, bodyH, widthM]} />
        <meshStandardMaterial {...mats.housing} />
      </mesh>
      {/* PCB plate under heatsink */}
      <mesh position={[0, plateCenterY, 0]} castShadow>
        <boxGeometry args={[lengthM * 0.94, plateH, widthM * 0.94]} />
        <meshStandardMaterial {...mats.board} />
      </mesh>
      {/* Individual LED dice */}
      <instancedMesh
        ref={diodeMeshRef}
        args={[undefined, undefined, diodeGrid.positions.length]}
        position={[0, diodeY, 0]}
        castShadow={false}
      >
        <boxGeometry
          args={[
            diodeGrid.radius * 1.6,
            diodeGrid.radius * 0.85,
            diodeGrid.radius * 1.6,
          ]}
        />
        <meshStandardMaterial {...mats.diode} />
      </instancedMesh>

      {/* Wide downward fill — replaces pointLight so it casts shadows but doesn't shine up */}
      <spotLight
        position={[0, lightY, 0]}
        angle={1.15}
        penumbra={1.0}
        intensity={fillI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castSpotShadow}
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0001}
        shadow-normalBias={0.02}
        shadow-radius={8}
      >
        <object3D attach="target" position={[0, lightY - 1.5, 0]} />
      </spotLight>
      {/* Broad downward wash — main canopy / wall key */}
      <spotLight
        position={[0, lightY, 0]}
        angle={1.15}
        penumbra={0.7}
        intensity={spotI}
        distance={0}
        decay={2}
        color={sceneColor}
        castShadow={castSpotShadow}
        shadow-mapSize={[2048, 2048]}
        shadow-camera-near={0.02}
        shadow-camera-far={8}
        shadow-bias={-0.0001}
        shadow-normalBias={0.02}
        shadow-radius={8}
      >
        <object3D attach="target" position={[0, lightY - 1.5, 0]} />
      </spotLight>
    </group>
  )
}
