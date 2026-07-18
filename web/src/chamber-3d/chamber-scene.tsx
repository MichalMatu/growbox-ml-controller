import {
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react"
import {
  Environment,
  Grid,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei"
import { Canvas, useStore } from "@react-three/fiber"
import {
  ACESFilmicToneMapping,
  SRGBColorSpace,
} from "three"

import { Enclosure } from "@/chamber-3d/enclosure"
import { ENCLOSURE_CM_MIN } from "@/chamber-3d/enclosure-cm"
import {
  getFeltPotPreset,
  type FeltPotPresetId,
} from "@/chamber-3d/felt-pot-geometry"
import { FeltPotGroup } from "@/chamber-3d/felt-pot"
import { GrowLight } from "@/chamber-3d/grow-light"
import {
  getLightPreset,
  type LightOrientationDeg,
  type LightPresetId,
  planLightFit,
} from "@/chamber-3d/light-geometry"
import {
  CHAMBER_CANVAS_CLASS,
  CHAMBER_MATERIAL,
  resolveChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

function RendererToneMapping({ exposure }: { exposure: number }) {
  const store = useStore()
  useLayoutEffect(() => {
    const { gl } = store.getState()
    gl.toneMapping = ACESFilmicToneMapping
    gl.toneMappingExposure = exposure
    gl.outputColorSpace = SRGBColorSpace
  }, [store, exposure])
  return null
}

export type ChamberSceneProps = {
  widthCm: number
  depthCm: number
  heightCm: number
  potPresetId?: FeltPotPresetId
  potCount?: number
  lightPresetId?: LightPresetId
  lightOrientationDeg?: LightOrientationDeg
  lightCeilingGapCm?: number
  lightOn?: boolean
}

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
  lightPresetId = "none",
  lightOrientationDeg = 0,
  lightCeilingGapCm = 5,
  lightOn = true,
}: ChamberSceneProps) {
  const themeClass = useDocumentThemeClass()
  const colors = useMemo(() => {
    void themeClass
    return resolveChamberSceneColors()
  }, [themeClass])
  const potPreset = useMemo(() => getFeltPotPreset(potPresetId), [potPresetId])
  const lightPreset = useMemo(
    () => getLightPreset(lightPresetId),
    [lightPresetId],
  )
  const maxSideM = Math.max(widthCm, depthCm, heightCm, 100) / 100
  const heightM = Math.max(heightCm, ENCLOSURE_CM_MIN) / 100
  const depthM = Math.max(depthCm, ENCLOSURE_CM_MIN) / 100
  const widthM = Math.max(widthCm, ENCLOSURE_CM_MIN) / 100
  const cameraDistance = maxSideM * 2.05

  const lightPlan = useMemo(
    () =>
      planLightFit(
        widthM,
        depthM,
        heightM,
        lightPreset,
        lightOrientationDeg,
        lightCeilingGapCm,
      ),
    [
      widthM,
      depthM,
      heightM,
      lightPreset,
      lightOrientationDeg,
      lightCeilingGapCm,
    ],
  )

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
        gl.setClearColor(0x000000, 0)
      }}
      dpr={[1, 1.75]}
    >
      <RendererToneMapping exposure={CHAMBER_MATERIAL.toneMappingExposure} />
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

      <ambientLight intensity={CHAMBER_MATERIAL.studioAmbientIntensity} />
      <hemisphereLight
        color={colors.interior}
        groundColor={colors.floor}
        intensity={CHAMBER_MATERIAL.studioHemisphereIntensity}
      />
      <directionalLight
        castShadow
        position={[maxSideM * 2.2, maxSideM * 3.2, maxSideM * 2.4]}
        intensity={CHAMBER_MATERIAL.studioKeyIntensity}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={maxSideM * 14}
        shadow-bias={-0.0002}
      />
      <directionalLight
        position={[0, heightM * 0.9, maxSideM * 3.0]}
        intensity={CHAMBER_MATERIAL.studioFrontIntensity}
      />
      <directionalLight
        position={[0, maxSideM * 3.8, maxSideM * 0.5]}
        intensity={CHAMBER_MATERIAL.studioTopIntensity}
      />
      <directionalLight
        position={[-maxSideM * 2.2, maxSideM * 1.9, maxSideM * 0.7]}
        intensity={CHAMBER_MATERIAL.studioRimLeftIntensity}
      />
      <directionalLight
        position={[maxSideM * 2.0, maxSideM * 1.6, -maxSideM * 1.0]}
        intensity={CHAMBER_MATERIAL.studioRimRightIntensity}
      />

      <Suspense fallback={null}>
        <Environment
          preset="warehouse"
          environmentIntensity={CHAMBER_MATERIAL.environmentIntensity}
          resolution={256}
        />
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
        {lightPlan.placement != null ? (
          <GrowLight
            preset={lightPreset}
            placement={lightPlan.placement}
            colors={colors}
            lit={lightOn}
            tentWidthM={widthM}
            tentDepthM={depthM}
            tentHeightM={heightM}
          />
        ) : null}
      </Suspense>

      {/*
        Stage floor + grid — default layer 0.
      */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[maxSideM * 6, maxSideM * 6]} />
        <meshStandardMaterial
          color={colors.floor}
          roughness={CHAMBER_MATERIAL.floorRoughness}
          metalness={CHAMBER_MATERIAL.floorMetalness}
          envMapIntensity={CHAMBER_MATERIAL.floorEnvMapIntensity}
        />
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
        minPolarAngle={0}
        maxPolarAngle={Math.PI * 0.92}
        minDistance={0.3}
        maxDistance={maxSideM * 8}
        zoomToCursor
      />
    </Canvas>
  )
}
