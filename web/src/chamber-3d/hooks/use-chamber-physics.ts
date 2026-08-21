import { useMemo } from "react"
import {
  clampFeltPotCount,
  getFeltPotPreset,
  maxPotsThatFit,
  type FeltPotCount,
  type FeltPotPresetId,
  type PotType,
} from "@/chamber-3d/components/pots/felt-pot-geometry"
import {
  getSquarePotPreset,
  maxSquarePotsThatFit,
  type SquarePotPresetId,
} from "@/chamber-3d/components/pots/square-pot-geometry"
import {
  clampCeilingGapCm,
  getLightPreset,
  listFittingOrientations,
  planLightFit,
  resolveLightOrientationDeg,
  type LightOrientationDeg,
  type LightPresetId,
} from "@/chamber-3d/components/lights/light-geometry"
import {
  FAN_CEILING_GAP_MIN_CM,
  clampFanCeilingGapCm,
  getFanPreset,
  listFittingFanOrientations,
  planFanFit,
  type FanOrientationDeg,
  type FanPosition,
  type FanPresetId,
  type LightAABB,
} from "@/chamber-3d/components/fans/fan-geometry"

export type PotKey = `${PotType}/${FeltPotPresetId | SquarePotPresetId}`

export function parsePotKey(key: string): { type: PotType; presetId: FeltPotPresetId | SquarePotPresetId } | null {
  const parts = key.split("/")
  if (parts.length !== 2) return null
  const type = parts[0]
  if (type !== "felt" && type !== "square") return null
  const presetId = parts[1]
  if (!["7l", "11l", "12l", "15l", "19l", "26l", "38l"].includes(presetId)) return null
  return { type: type as PotType, presetId: presetId as FeltPotPresetId | SquarePotPresetId }
}

export type ChamberPhysicsProps = {
  widthCm: number
  depthCm: number
  heightCm: number
  potKey: PotKey
  defaultPotKey: PotKey
  potCount: FeltPotCount
  lightPresetId: LightPresetId
  lightOrientationDeg: LightOrientationDeg
  lightCeilingGapCm: number
  fanPresetId: FanPresetId
  fanOrientationDeg: FanOrientationDeg
  fanCeilingGapCm: number
  fanPosition: FanPosition
}

export function useChamberPhysics(props: ChamberPhysicsProps) {
  const {
    widthCm,
    depthCm,
    heightCm,
    potKey,
    defaultPotKey,
    potCount,
    lightPresetId,
    lightOrientationDeg,
    lightCeilingGapCm,
    fanPresetId,
    fanOrientationDeg,
    fanCeilingGapCm,
    fanPosition,
  } = props

  const volumeM3 = useMemo(
    () => (widthCm * depthCm * heightCm) / 1_000_000,
    [widthCm, depthCm, heightCm],
  )

  const potKeyParsed = useMemo(() => {
    const parsed = parsePotKey(potKey)
    if (parsed) return parsed
    // Fallback
    const fallback = parsePotKey(defaultPotKey)
    if (!fallback) throw new Error(`Invalid DEFAULT_POT_KEY: ${defaultPotKey}`)
    return fallback
  }, [potKey, defaultPotKey])

  const potType = potKeyParsed.type
  const potPresetId = potKeyParsed.presetId

  const potPreset = useMemo(() => getFeltPotPreset(potPresetId as FeltPotPresetId), [potPresetId])
  const squarePotPreset = useMemo(() => getSquarePotPreset(potPresetId as SquarePotPresetId), [potPresetId])

  const maxFit = useMemo(() => {
    const w = widthCm / 100
    const d = depthCm / 100
    const h = heightCm / 100
    if (potType === "square") {
      return maxSquarePotsThatFit(w, d, h, {
        sideCm: squarePotPreset.sideCm,
        heightCm: squarePotPreset.heightCm,
      })
    }
    return maxPotsThatFit(w, d, h, {
      diameterCm: potPreset.diameterCm,
      heightCm: potPreset.heightCm,
    })
  }, [widthCm, depthCm, heightCm, potType, potPreset.diameterCm, potPreset.heightCm, squarePotPreset.sideCm, squarePotPreset.heightCm])

  const visiblePotCount = clampFeltPotCount(Math.min(potCount, maxFit))

  const potMaxHeightCm = useMemo(() => {
    if (visiblePotCount === 0) return 0
    if (potType === "square") return squarePotPreset.heightCm
    return potPreset.heightCm
  }, [visiblePotCount, potType, potPreset.heightCm, squarePotPreset.heightCm])

  const lightPreset = useMemo(() => getLightPreset(lightPresetId), [lightPresetId])
  const fanPreset = useMemo(() => getFanPreset(fanPresetId), [fanPresetId])

  const baseFanGap = useMemo(
    () => clampFanCeilingGapCm(fanCeilingGapCm, heightCm / 100, fanPreset.bodyDiameterCm, potMaxHeightCm),
    [fanCeilingGapCm, heightCm, fanPreset.bodyDiameterCm, potMaxHeightCm],
  )

  const effectiveCeilingGapCm = useMemo(
    () => clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm, potMaxHeightCm),
    [lightCeilingGapCm, heightCm, lightPreset.heightCm, potMaxHeightCm],
  )

  const fittingOrientations = useMemo(
    () =>
      listFittingOrientations(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        effectiveCeilingGapCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, effectiveCeilingGapCm],
  )

  const effectiveLightOrientationDeg = useMemo(
    () =>
      resolveLightOrientationDeg(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        lightOrientationDeg,
        effectiveCeilingGapCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, lightOrientationDeg, effectiveCeilingGapCm],
  )

  const fanFittingOrientations = useMemo(
    () =>
      listFittingFanOrientations(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        baseFanGap,
      ),
    [widthCm, depthCm, heightCm, fanPreset, baseFanGap],
  )

  const effectiveFanOrientationDeg = useMemo(() => {
    if (fanPreset.form === "none") return fanOrientationDeg
    if (fanFittingOrientations.length === 0) return fanOrientationDeg
    if (fanFittingOrientations.includes(fanOrientationDeg)) return fanOrientationDeg
    return fanFittingOrientations[0]!
  }, [fanPreset.form, fanFittingOrientations, fanOrientationDeg])

  const fanOnlyPlan = useMemo(
    () =>
      planFanFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        effectiveFanOrientationDeg,
        baseFanGap,
        null,
        fanPosition,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, fanPreset, effectiveFanOrientationDeg, baseFanGap, fanPosition, potMaxHeightCm],
  )

  const baseLightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        effectiveLightOrientationDeg,
        clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm, potMaxHeightCm),
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, effectiveLightOrientationDeg, lightCeilingGapCm, potMaxHeightCm],
  )

  const hasHorizontalOverlap = useMemo(() => {
    if (lightPreset.form === "none" || fanPreset.form === "none") return false
    if (!fanOnlyPlan.placement || !baseLightPlan.placement) return false
    const fan = fanOnlyPlan.placement
    const light = baseLightPlan.placement
    const overlapX =
      Math.abs(fan.x - light.x) < (fan.extentXM + light.extentXM) / 2 + 0.02
    const overlapZ =
      Math.abs(fan.z - light.z) < (fan.extentZM + light.extentZM) / 2 + 0.02
    return overlapX && overlapZ
  }, [lightPreset.form, fanPreset.form, fanOnlyPlan.placement, baseLightPlan.placement])

  const { effectiveFanCeilingGapCm, effectiveLightCeilingGapCm } = useMemo(() => {
    const baseLightGap = clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm, potMaxHeightCm)
    const baseFanGap = clampFanCeilingGapCm(fanCeilingGapCm, heightCm / 100, fanPreset.bodyDiameterCm, potMaxHeightCm)

    if (!hasHorizontalOverlap) {
      return {
        effectiveFanCeilingGapCm: baseFanGap,
        effectiveLightCeilingGapCm: baseLightGap,
      }
    }

    const maxAllowedFanGap = Math.floor(baseLightGap - fanPreset.bodyDiameterCm - 2)

    if (maxAllowedFanGap >= FAN_CEILING_GAP_MIN_CM) {
      const fanGap = Math.min(baseFanGap, maxAllowedFanGap)
      return {
        effectiveFanCeilingGapCm: fanGap,
        effectiveLightCeilingGapCm: baseLightGap,
      }
    } else {
      const fanGap = FAN_CEILING_GAP_MIN_CM
      const minRequiredLightGap = Math.ceil(FAN_CEILING_GAP_MIN_CM + fanPreset.bodyDiameterCm + 2)
      const lightGap = Math.min(
        Math.max(baseLightGap, minRequiredLightGap),
        baseLightPlan.maxCeilingGapCm
      )
      return {
        effectiveFanCeilingGapCm: fanGap,
        effectiveLightCeilingGapCm: lightGap,
      }
    }
  }, [hasHorizontalOverlap, lightCeilingGapCm, fanCeilingGapCm, heightCm, lightPreset.heightCm, fanPreset.bodyDiameterCm, potMaxHeightCm, baseLightPlan.maxCeilingGapCm])

  const lightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        effectiveLightOrientationDeg,
        effectiveLightCeilingGapCm,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, effectiveLightOrientationDeg, effectiveLightCeilingGapCm, potMaxHeightCm],
  )

  const lightAABB: LightAABB | null = useMemo(() => {
    if (lightPlan.placement == null || lightPreset.form === "none") return null
    return {
      centerX: lightPlan.placement.x,
      centerY: lightPlan.placement.y,
      centerZ: lightPlan.placement.z,
      extentXM: lightPlan.placement.extentXM,
      extentZM: lightPlan.placement.extentZM,
      heightM: lightPlan.placement.heightM,
    }
  }, [lightPlan.placement, lightPreset.form])

  const fanPlan = useMemo(
    () =>
      planFanFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        effectiveFanOrientationDeg,
        effectiveFanCeilingGapCm,
        lightAABB,
        fanPosition,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, fanPreset, effectiveFanOrientationDeg, effectiveFanCeilingGapCm, lightAABB, fanPosition, potMaxHeightCm],
  )

  return {
    volumeM3,
    potType,
    potPreset,
    squarePotPreset,
    maxFit,
    visiblePotCount,
    potMaxHeightCm,
    lightPreset,
    fanPreset,
    fittingOrientations,
    effectiveLightOrientationDeg,
    fanFittingOrientations,
    effectiveFanOrientationDeg,
    lightPlan,
    fanPlan,
    effectiveLightCeilingGapCm,
    effectiveFanCeilingGapCm,
    baseLightPlan, // Used for limits
    fanOnlyPlan, // Used for limits
    hasHorizontalOverlap,
    potPresetId,
  }
}
