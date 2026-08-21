import {
  type LightForm,
  type LightPlacementM,
  type LightPreset,
} from "@/chamber-3d/components/lights/light-geometry"
import { useChamberPerformance } from "@/chamber-3d/performance/performance-context"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"

import { LedPanelMesh } from "./led-panel"
import { HpsBoxMesh } from "./hps-box"
import { HpsWingMesh } from "./hps-wing"
import { HpsCooltubeMesh } from "./hps-cooltube"

export type GrowLightProps = {
  preset: LightPreset
  placement: LightPlacementM
  colors: ChamberSceneColors
  /** When true, diodes/bulb glow and real scene lights turn on. */
  lit?: boolean
  /** Tent AABB (meters) — clamps light distance to the interior volume. */
  tentWidthM: number
  tentDepthM: number
  tentHeightM: number
}

/**
 * Max useful reach from a ceiling fixture to the far interior corner.
 * Prevents multi-meter fixture “reach” spheres that light the stage pad
 * (layers also isolate the pad; distance keeps falloff natural inside).
 */
function interiorLightReachM(
  tentWidthM: number,
  tentDepthM: number,
  lightWorldY: number,
): number {
  const halfW = tentWidthM * 0.5
  const halfD = tentDepthM * 0.5
  const toFarCorner = Math.hypot(halfW, halfD, Math.max(lightWorldY, 0.15))
  return toFarCorner * 1.1
}



/**
 * Soft power curve so 1000 W reads stronger than 600 W without blowing foil.
 * Reference watts live in CHAMBER_MATERIAL (LED 200 / HPS 600).
 */
function fixturePowerScale(preset: LightPreset): number {
  if (preset.form === "none" || preset.powerW <= 0) return 0
  const refW =
    preset.form === "led_panel"
      ? CHAMBER_MATERIAL.ledPowerRefW
      : CHAMBER_MATERIAL.hpsPowerRefW
  // Use linear power scaling instead of Math.sqrt so wattage differences (e.g. 600W vs 1000W)
  // are strongly visible and realistic in the 3D scene without artificial compression.
  return preset.powerW / refW
}

function hpsFormScale(form: LightForm): number {
  switch (form) {
    case "hps_box":
      return CHAMBER_MATERIAL.hpsFormScaleBox
    case "hps_wing":
      return CHAMBER_MATERIAL.hpsFormScaleWing
    case "hps_cooltube":
      return CHAMBER_MATERIAL.hpsFormScaleCooltube
    default:
      return 1
  }
}

/**
 * Parametric grow-light fixture from catalog AABB.
 * LED: diode grid + multi-point fill from the panel face.
 * HPS: single bulb source + spot + reflective hood/wing materials.
 * Local space: length +X, width +Z, height +Y; group applies yaw.
 */
export function GrowLight({
  preset,
  placement,
  colors,
  lit = true,
  tentWidthM,
  tentDepthM,
  tentHeightM,
}: GrowLightProps) {
  const { config } = useChamberPerformance()

  if (preset.form === "none") return null

  const lengthM = preset.lengthCm / 100
  const widthM = preset.widthCm / 100
  const heightM = preset.heightCm / 100
  const powerScale = fixturePowerScale(preset)
  const formScale = hpsFormScale(preset.form)
  // Emitter sits near the bottom of the AABB; world Y ≈ placement.y - body/2.
  const emitterWorldY = Math.max(
    0.12,
    placement.y - heightM * 0.35,
  )
  const maxReachM = interiorLightReachM(
    tentWidthM,
    tentDepthM,
    emitterWorldY,
  )
  void tentHeightM

  return (
    <group
      position={[placement.x, placement.y, placement.z]}
      rotation={[0, placement.rotationYRad, 0]}
    >
      {preset.form === "led_panel" ? (
        <LedPanelMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale}
        />
      ) : null}
      {preset.form === "hps_box" ? (
        <HpsBoxMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
      {preset.form === "hps_wing" ? (
        <HpsWingMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
      {preset.form === "hps_cooltube" ? (
        <HpsCooltubeMesh
          lengthM={lengthM}
          widthM={widthM}
          heightM={heightM}
          ductDiameterCm={preset.ductDiameterCm ?? 12.5}
          colors={colors}
          lit={lit}
          fixtureShadows={config.fixtureShadows}
          powerScale={powerScale * formScale}
          maxReachM={maxReachM}
        />
      ) : null}
    </group>
  )
}
