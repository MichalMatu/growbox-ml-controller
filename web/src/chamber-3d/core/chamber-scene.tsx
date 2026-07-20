import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { Environment, Grid, OrbitControls, PerspectiveCamera } from "@react-three/drei"
import { Canvas, useFrame, useStore } from "@react-three/fiber"
import { ACESFilmicToneMapping, SRGBColorSpace } from "three"

import { reportFps } from "@/chamber-3d/core/fps-bridge"
import { Enclosure } from "@/chamber-3d/components/enclosure/enclosure"
import { ENCLOSURE_CM_MIN } from "@/chamber-3d/components/enclosure/enclosure-cm"
import { getFeltPotPreset, type FeltPotPresetId } from "@/chamber-3d/components/pots/felt-pot-geometry"
import { FeltPotGroup } from "@/chamber-3d/components/pots/felt-pot"
import { GrowLight } from "@/chamber-3d/components/lights"
import { getLightPreset, type LightOrientationDeg, type LightPresetId, planLightFit } from "@/chamber-3d/components/lights/light-geometry"
import { ChamberPerformanceProvider, useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { Room, type RoomLayout } from "@/chamber-3d/environment/room"
import { CHAMBER_CANVAS_CLASS, CHAMBER_MATERIAL, resolveChamberSceneColors } from "@/chamber-3d/core/scene-tokens"

/** Internal scene — expects a ChamberPerformanceProvider ancestor. */
export function ChamberCanvas({
  widthCm,
  depthCm,
  heightCm,
  potPresetId = "12l",
  potCount = 0,
  lightPresetId = "none",
  lightOrientationDeg = 0,
  lightCeilingGapCm = 5,
  lightOn = true,
  roomLayout = "none",
}: ChamberSceneProps) {
  const { config } = useChamberPerformance()
  const themeClass = useDocumentThemeClass()
  const colors = useMemo(() => {
    void themeClass
    return resolveChamberSceneColors()
  }, [themeClass])
  const potPreset = useMemo(() => getFeltPotPreset(potPresetId), [potPresetId])
  const lightPreset = useMemo(() => getLightPreset(lightPresetId), [lightPresetId])
  const roomActive = roomLayout !== "none"
  const maxSideM = Math.max(widthCm, depthCm, heightCm, 100) / 100
  const heightM = Math.max(heightCm, ENCLOSURE_CM_MIN) / 100
  const depthM = Math.max(depthCm, ENCLOSURE_CM_MIN) / 100
  const widthM = Math.max(widthCm, ENCLOSURE_CM_MIN) / 100
  const cameraDistance = maxSideM * 2.05

  const lightPlan = useMemo(
    () =>
      planLightFit(widthM, depthM, heightM, lightPreset, lightOrientationDeg, lightCeilingGapCm),
    [widthM, depthM, heightM, lightPreset, lightOrientationDeg, lightCeilingGapCm],
  )

  // DPR floor = 1.0 at minimum — sub-1.0 DPR makes text and thin lines
  // unreadable on Retina/4K displays. GPU savings on Low tier come from
  // reduced shadows, geometry, and lights; not from sub-pixel rendering.
  const dprMin = Math.max(1.0, config.dprMax / 2)
  const dprMax = config.dprMax

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
        // PCFSoftShadowMap (2) supports shadow-radius for per-light blur.
        // PCFShadowMap (1) ignores shadow-radius entirely.
        gl.shadowMap.type = 2 // PCFSoftShadowMap
      }}
      dpr={[dprMin, dprMax]}
    >
      <RendererToneMapping exposure={config.toneMappingExposure} />
      {config.fog ? <fog attach="fog" args={[colors.fog, maxSideM * 5.5, maxSideM * 15]} /> : null}

      <PerspectiveCamera
        makeDefault
        position={[cameraDistance * 0.55, cameraDistance * 0.4, cameraDistance * 0.98]}
        fov={38}
        near={0.01}
        far={100}
      />

      {/* Studio lights — count controlled by tier. Environment map is always on
          (minimum 32×32 even on Low) so metallic foil materials always have IBL. */}
      <ambientLight intensity={CHAMBER_MATERIAL.studioAmbientIntensity * 0.9} />
      {config.studioLightCount >= 1 && (
        <hemisphereLight
          color={colors.interior}
          groundColor={colors.floor}
          intensity={CHAMBER_MATERIAL.studioHemisphereIntensity}
        />
      )}
      {config.studioLightCount >= 2 && (
        <directionalLight
          castShadow
          position={[maxSideM * 2.2, maxSideM * 3.2, maxSideM * 2.4]}
          intensity={CHAMBER_MATERIAL.studioKeyIntensity}
          shadow-mapSize-width={config.shadowMapSize}
          shadow-mapSize-height={config.shadowMapSize}
          shadow-camera-near={0.01}
          shadow-camera-far={maxSideM * 14}
          shadow-camera-left={-maxSideM * 2.5}
          shadow-camera-right={maxSideM * 2.5}
          shadow-camera-top={maxSideM * 2.5}
          shadow-camera-bottom={-maxSideM * 2.5}
          shadow-bias={-0.0001}
          shadow-normalBias={0}
          shadow-radius={4}
        />
      )}
      {config.studioLightCount >= 3 && (
        <directionalLight
          position={[0, heightM * 0.9, maxSideM * 3.0]}
          intensity={CHAMBER_MATERIAL.studioFrontIntensity}
        />
      )}
      {config.studioLightCount >= 4 && (
        <directionalLight
          position={[0, maxSideM * 3.8, maxSideM * 0.5]}
          intensity={CHAMBER_MATERIAL.studioTopIntensity}
        />
      )}
      {config.studioLightCount >= 5 && (
        <directionalLight
          position={[-maxSideM * 2.2, maxSideM * 1.9, maxSideM * 0.7]}
          intensity={CHAMBER_MATERIAL.studioRimLeftIntensity}
        />
      )}
      {config.studioLightCount >= 6 && (
        <directionalLight
          position={[maxSideM * 2.0, maxSideM * 1.6, -maxSideM * 1.0]}
          intensity={CHAMBER_MATERIAL.studioRimRightIntensity}
        />
      )}

      <Suspense fallback={null}>
        {config.environmentMap && (
          <Environment
            preset="warehouse"
            environmentIntensity={CHAMBER_MATERIAL.environmentIntensity}
            resolution={config.environmentResolution}
          />
        )}
        <Room
          layout={roomLayout}
          colors={colors}
          tentHalfM={{
            width: widthM / 2,
            depth: depthM / 2,
            height: heightM,
          }}
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

      {/* Stage floor — hidden when room provides architectural context */}
      {!roomActive && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <planeGeometry args={[maxSideM * 6, maxSideM * 6]} />
          <meshStandardMaterial
            color={colors.floor}
            roughness={CHAMBER_MATERIAL.floorRoughness}
            metalness={CHAMBER_MATERIAL.floorMetalness}
            envMapIntensity={config.environmentMap ? CHAMBER_MATERIAL.floorEnvMapIntensity : 0}
          />
        </mesh>
      )}

      {config.floorGrid && !roomActive && (
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
      )}

      <OrbitControls
        makeDefault
        target={[0, heightM * 0.42, 0]}
        minPolarAngle={0}
        maxPolarAngle={Math.PI * 0.92}
        minDistance={0.3}
        maxDistance={maxSideM * 8}
        zoomToCursor
      />

      <FpsReporter />
    </Canvas>
  )
}

/**
 * Measures actual WebGL frame times via R3F's useFrame (fires only when
 * Three.js completes a render pass). Writes to the shared fps-bridge store
 * so the DOM overlay reads real GPU-bound FPS, not browser rAF rate.
 */
function FpsReporter() {
  const lastRef = useRef(0)
  const smoothRef = useRef(60)
  const frameRef = useRef(0)
  const warmedUp = useRef(false)

  useFrame(() => {
    const now = performance.now()
    // Seed on first call (useRef cannot call performance.now during render)
    if (lastRef.current === 0) {
      lastRef.current = now
      return
    }
    const elapsed = now - lastRef.current
    lastRef.current = now

    frameRef.current++

    if (elapsed > 0 && frameRef.current > 10) {
      const instant = 1000 / elapsed
      smoothRef.current = smoothRef.current * 0.9 + instant * 0.1
    }

    if (frameRef.current >= 30) warmedUp.current = true

    // Sync to bridge every 8 frames (~130 ms at 60 fps)
    if (frameRef.current % 8 === 0) {
      reportFps(smoothRef.current)
    }
  })

  return null
}

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
  roomLayout?: RoomLayout
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

/**
 * Self-contained scene (backwards-compatible entry point).
 * If you already have a ChamberPerformanceProvider ancestor (e.g.
 * to share with a debug overlay), use `<ChamberCanvas>` directly.
 */
export function ChamberScene(props: ChamberSceneProps) {
  return (
    <ChamberPerformanceProvider>
      <ChamberCanvas {...props} />
    </ChamberPerformanceProvider>
  )
}
