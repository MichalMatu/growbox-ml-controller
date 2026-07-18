import { Grid, OrbitControls, PerspectiveCamera } from "@react-three/drei"
import { Canvas } from "@react-three/fiber"

import { Enclosure, type EnclosureDimensions } from "@/chamber-3d/enclosure"
import { CHAMBER_CANVAS_CLASS, CHAMBER_SCENE } from "@/chamber-3d/scene-tokens"

type ChamberSceneProps = EnclosureDimensions

export function ChamberScene({ widthCm, depthCm, heightCm }: ChamberSceneProps) {
  const maxSideM = Math.max(widthCm, depthCm, heightCm, 100) / 100
  const cameraDistance = maxSideM * 2.4

  return (
    <Canvas shadows className={CHAMBER_CANVAS_CLASS}>
      <color attach="background" args={[CHAMBER_SCENE.background]} />
      <fog attach="fog" args={[CHAMBER_SCENE.fog, maxSideM * 4, maxSideM * 12]} />

      <PerspectiveCamera
        makeDefault
        position={[cameraDistance * 0.75, cameraDistance * 0.55, cameraDistance * 0.9]}
        fov={45}
        near={0.01}
        far={100}
      />

      <ambientLight intensity={0.45} />
      <directionalLight
        castShadow
        position={[maxSideM * 1.5, maxSideM * 2.2, maxSideM * 1.2]}
        intensity={1.15}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />

      <Enclosure widthCm={widthCm} depthCm={depthCm} heightCm={heightCm} />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[maxSideM * 6, maxSideM * 6]} />
        <meshStandardMaterial color={CHAMBER_SCENE.floor} />
      </mesh>

      <Grid
        args={[maxSideM * 6, maxSideM * 6]}
        cellSize={0.1}
        cellThickness={0.6}
        cellColor={CHAMBER_SCENE.gridCell}
        sectionSize={0.5}
        sectionThickness={1}
        sectionColor={CHAMBER_SCENE.gridSection}
        fadeDistance={maxSideM * 5}
        fadeStrength={1.2}
        infiniteGrid
        position={[0, 0.001, 0]}
      />

      <OrbitControls
        makeDefault
        target={[0, (heightCm / 100) * 0.4, 0]}
        maxPolarAngle={Math.PI * 0.49}
        minDistance={0.3}
        maxDistance={maxSideM * 8}
      />
    </Canvas>
  )
}
