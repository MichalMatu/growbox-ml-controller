import {
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
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
  type Group,
  type Light,
  type Object3D,
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
  CHAMBER_LAYER,
  CHAMBER_MATERIAL,
  resolveChamberSceneColors,
} from "@/chamber-3d/scene-tokens"

/**
 * ACES filmic grade + exposure. Read the R3F store (not useThree selector) so
 * WebGLRenderer can be updated without react-hooks/immutability violations.
 */
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

function applyLayers(object: Object3D, layers: readonly number[]): void {
  object.layers.disableAll()
  for (const layer of layers) {
    object.layers.enable(layer)
  }
}

/** Camera must see content (0) + exterior stage floor/grid (1). */
function CameraLayers() {
  const store = useStore()
  useLayoutEffect(() => {
    const { camera } = store.getState()
    camera.layers.enable(CHAMBER_LAYER.content)
    camera.layers.enable(CHAMBER_LAYER.stage)
  }, [store])
  return null
}

/**
 * Studio lights hit tent content AND the exterior pad.
 * Grow fixture lights stay on layer 0 only (Three default) — they never
 * illuminate the stage floor, so no circular bleed around the tent.
 */
function studioLightRef(light: Light | null): void {
  if (!light) return
  applyLayers(light, [CHAMBER_LAYER.content, CHAMBER_LAYER.stage])
}

/** Floor + grid: stage layer only — invisible to grow fixture lights. */
function StageOnly({ children }: { children: ReactNode }) {
  const ref = useRef<Group>(null)
  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    root.traverse((obj) => {
      applyLayers(obj, [CHAMBER_LAYER.stage])
    })
  })
  return <group ref={ref}>{children}</group>
}

export type ChamberSceneProps = {
  widthCm: number
  depthCm: number
  heightCm: number
  /** Felt pot catalog id (playground only). */
  potPresetId?: FeltPotPresetId
  /** How many pots to try to place (0–4); packing may place fewer. */
  potCount?: number
  /** Grow-light catalog id (playground only; not v4 actuators.lights). */
  lightPresetId?: LightPresetId
  lightOrientationDeg?: LightOrientationDeg
  /** Gap from inner roof to top of fixture (cm). */
  lightCeilingGapCm?: number
  /** Emitter / bulb glow on. */
  lightOn?: boolean
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
  lightPresetId = "none",
  lightOrientationDeg = 0,
  lightCeilingGapCm = 5,
  lightOn = true,
}: ChamberSceneProps) {
  const themeClass = useDocumentThemeClass()
  /** Re-read CSS tokens after <html> light/dark class is applied. */
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

  /** Fixture installed (fits) — not the same as “Świeci”. */
  const hasGrowFixture =
    lightPlan.placement != null && lightPreset.form !== "none"
  const growLit = lightOn && hasGrowFixture
  /** Exterior studio fill: full / mounted-off / residual when grow-lit. */
  const studioScale = growLit
    ? CHAMBER_MATERIAL.studioScaleGrowLit
    : hasGrowFixture
      ? CHAMBER_MATERIAL.studioScaleFixtureOff
      : CHAMBER_MATERIAL.studioScaleEmpty
  const toneMappingExposure = growLit
    ? CHAMBER_MATERIAL.toneMappingExposureGrowLit
    : CHAMBER_MATERIAL.toneMappingExposureStudio

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
      <RendererToneMapping exposure={toneMappingExposure} />
      <CameraLayers />
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

      <ambientLight ref={studioLightRef} intensity={0.75 * studioScale} />
      <hemisphereLight
        ref={studioLightRef}
        color={colors.interior}
        groundColor={colors.floor}
        intensity={0.55 * studioScale}
      />

      <directionalLight
        ref={studioLightRef}
        castShadow
        position={[maxSideM * 1.6, maxSideM * 2.8, maxSideM * 2]}
        intensity={1.55 * studioScale}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={maxSideM * 12}
        shadow-bias={-0.0002}
      />
      <directionalLight
        ref={studioLightRef}
        position={[0.15, heightM * 0.5, depthM * 2.6]}
        intensity={1.1 * studioScale}
      />
      {/* Soft side rims only — black exterior should not catch hard specular */}
      <directionalLight
        ref={studioLightRef}
        position={[-maxSideM * 1.8, maxSideM * 1.6, maxSideM * 0.6]}
        intensity={0.55 * studioScale}
      />
      <directionalLight
        ref={studioLightRef}
        position={[maxSideM * 1.6, maxSideM * 1.3, -maxSideM * 0.8]}
        intensity={0.35 * studioScale}
      />

      {/*
        Ceiling / upper-panel studio lights (point + spot from tent roof).
        Omit entirely when a grow fixture is installed — they fight the lamp
        and look like a second light from the top panel.
      */}
      {!hasGrowFixture ? (
        <>
          <pointLight
            ref={studioLightRef}
            position={[0, heightM * 0.9, 0]}
            intensity={4.2}
            distance={Math.max(widthM, depthM, heightM) * 3.2}
            decay={2}
          />
          <pointLight
            ref={studioLightRef}
            position={[0, heightM * 0.45, depthM * 0.15]}
            intensity={2.0}
            distance={Math.max(widthM, depthM) * 2}
            decay={2}
          />
          <spotLight
            ref={studioLightRef}
            position={[0, heightM * 0.96, depthM * 0.02]}
            angle={0.9}
            penumbra={0.55}
            intensity={2.8}
            distance={heightM * 2.8}
            castShadow
          >
            <object3D attach="target" position={[0, 0, 0]} />
          </spotLight>
        </>
      ) : null}

      <Suspense fallback={null}>
        {/* Warehouse HDR inside Suspense so PMREM + maps load without racing the canvas */}
        <Environment
          preset="warehouse"
          environmentIntensity={
            growLit
              ? CHAMBER_MATERIAL.environmentIntensityGrowLit
              : hasGrowFixture
                ? CHAMBER_MATERIAL.environmentIntensityFixtureOff
                : CHAMBER_MATERIAL.environmentIntensityEmpty
          }
          resolution={128}
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
        Stage pad is layer-isolated from grow fixture lights (see CHAMBER_LAYER).
        Without this, every point/spot paints a bright circle through the walls
        onto the continuous floor plane — Three.js lights ignore occlusion.
      */}
      <StageOnly>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <planeGeometry args={[maxSideM * 6, maxSideM * 6]} />
          <meshStandardMaterial
            color={colors.floor}
            roughness={0.9}
            metalness={0.04}
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
      </StageOnly>

      <OrbitControls
        makeDefault
        target={[0, heightM * 0.42, 0]}
        // Allow looking up at the ceiling (past horizontal); keep a small floor
        // clamp so the camera does not fully tumble under the ground plane.
        minPolarAngle={0}
        maxPolarAngle={Math.PI * 0.92}
        minDistance={0.3}
        maxDistance={maxSideM * 8}
        // Wheel zoom toward the point under the cursor (not scene center).
        zoomToCursor
      />
    </Canvas>
  )
}
