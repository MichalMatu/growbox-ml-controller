import { Suspense, useEffect, useMemo, useState } from "react"
import {
  Environment,
  Grid,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei"
import { Canvas } from "@react-three/fiber"

import { Enclosure } from "@/chamber-3d/enclosure"
import { ENCLOSURE_CM_MIN } from "@/chamber-3d/enclosure-cm"
import {
  getFeltPotPreset,
  type FeltPotPresetId,
} from "@/chamber-3d/felt-pot-geometry"
import { FeltPotGroup } from "@/chamber-3d/felt-pot"
import {
  CHAMBER_CANVAS_CLASS,
  resolveChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

export type ChamberSceneProps = {
  widthCm: number
  depthCm: number
  heightCm: number
  /** Felt pot catalog id (playground only). */
  potPresetId?: FeltPotPresetId
  /** How many pots to try to place (0–4); packing may place fewer. */
  potCount?: number
}

/** Track actual <html> light/dark class (after ThemeProvider applyTheme). */
function useDocumentThemeClass(): "light" | "dark" {
  const [themeClass, setThemeClass] = useState<"light" | "dark">(() => {
    if (typeof document === "undefined") return "dark"
    return document.documentElement.classList.contains("dark") ? "dark" : "light"
  })

  useEffect(() => {
    const root = document.documentElement
    const sync = () => {
      setThemeClass(root.classList.contains("dark") ? "dark" : "light")
    }
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(root, { attributes: true, attributeFilter: ["class"] })
    return () => observer.disconnect()
  }, [])

  return themeClass
}

export function ChamberScene({
  widthCm,
  depthCm,
  heightCm,
  potPresetId = "12l",
  potCount = 0,
}: ChamberSceneProps) {
  const themeClass = useDocumentThemeClass()
  /** Re-read CSS tokens after <html> light/dark class is applied. */
  const colors = useMemo(() => {
    void themeClass
    return resolveChamberSceneColors()
  }, [themeClass])
  const potPreset = useMemo(() => getFeltPotPreset(potPresetId), [potPresetId])
  const maxSideM = Math.max(widthCm, depthCm, heightCm, 100) / 100
  const heightM = Math.max(heightCm, ENCLOSURE_CM_MIN) / 100
  const depthM = Math.max(depthCm, ENCLOSURE_CM_MIN) / 100
  const widthM = Math.max(widthCm, ENCLOSURE_CM_MIN) / 100
  const cameraDistance = maxSideM * 2.05

  return (
    <Canvas
      shadows
      className={CHAMBER_CANVAS_CLASS}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      }}
      onCreated={({ gl }) => {
        /* Transparent clear so CSS --chamber-bg-gradient shows through */
        gl.setClearColor(0x000000, 0)
      }}
      dpr={[1, 1.75]}
    >
      <fog attach="fog" args={[colors.fog, maxSideM * 5.5, maxSideM * 15]} />

      <PerspectiveCamera
        makeDefault
        position={[
          cameraDistance * 0.55,
          cameraDistance * 0.4,
          cameraDistance * 0.98,
        ]}
        fov={38}
        near={0.01}
        far={100}
      />

      <ambientLight intensity={0.75} />
      <hemisphereLight
        color={colors.interior}
        groundColor={colors.floor}
        intensity={0.55}
      />

      <directionalLight
        castShadow
        position={[maxSideM * 1.6, maxSideM * 2.8, maxSideM * 2]}
        intensity={1.55}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={maxSideM * 12}
        shadow-bias={-0.0002}
      />
      <directionalLight
        position={[0.15, heightM * 0.5, depthM * 2.6]}
        intensity={1.1}
      />
      {/* Soft side rims only — black exterior should not catch hard specular */}
      <directionalLight
        position={[-maxSideM * 1.8, maxSideM * 1.6, maxSideM * 0.6]}
        intensity={0.55}
      />
      <directionalLight
        position={[maxSideM * 1.6, maxSideM * 1.3, -maxSideM * 0.8]}
        intensity={0.35}
      />

      {/* Internal fill — bright silver mylar needs strong white bounce */}
      <pointLight
        position={[0, heightM * 0.9, 0]}
        intensity={4.2}
        distance={Math.max(widthM, depthM, heightM) * 3.2}
        decay={2}
      />
      <pointLight
        position={[0, heightM * 0.45, depthM * 0.15]}
        intensity={2.0}
        distance={Math.max(widthM, depthM) * 2}
        decay={2}
      />
      <spotLight
        position={[0, heightM * 0.96, depthM * 0.02]}
        angle={0.9}
        penumbra={0.55}
        intensity={2.8}
        distance={heightM * 2.8}
        castShadow
      >
        <object3D attach="target" position={[0, 0, 0]} />
      </spotLight>

      <Suspense fallback={null}>
        {/* Warehouse HDR inside Suspense so PMREM + maps load without racing the canvas */}
        <Environment preset="warehouse" environmentIntensity={0.7} resolution={128} />
        <Enclosure
          widthCm={widthCm}
          depthCm={depthCm}
          heightCm={heightCm}
          colors={colors}
        />
        <FeltPotGroup
          widthM={widthM}
          depthM={depthM}
          heightM={heightM}
          preset={potPreset}
          count={potCount}
          colors={colors}
        />
      </Suspense>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[maxSideM * 6, maxSideM * 6]} />
        <meshStandardMaterial color={colors.floor} roughness={0.9} metalness={0.04} />
      </mesh>

      <Grid
        args={[maxSideM * 6, maxSideM * 6]}
        cellSize={0.1}
        cellThickness={0.5}
        cellColor={colors.gridCell}
        sectionSize={0.5}
        sectionThickness={1}
        sectionColor={colors.gridSection}
        fadeDistance={maxSideM * 5}
        fadeStrength={1.2}
        infiniteGrid
        position={[0, 0.001, 0]}
      />

      <OrbitControls
        makeDefault
        target={[0, heightM * 0.42, 0]}
        maxPolarAngle={Math.PI * 0.49}
        minDistance={0.3}
        maxDistance={maxSideM * 8}
        // Wheel zoom toward the point under the cursor (not scene center).
        zoomToCursor
      />
    </Canvas>
  )
}
