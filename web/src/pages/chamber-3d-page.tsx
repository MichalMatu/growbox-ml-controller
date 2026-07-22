import { useMemo, useState } from "react"

import { ChamberCanvas } from "@/chamber-3d/core/chamber-scene"
import { ChamberPerformanceProvider } from "@/chamber-3d/performance/performance-context"
import { PerformanceOverlay } from "@/chamber-3d/performance/performance-overlay"
import { type RoomLayout } from "@/chamber-3d/environment/room"
import {
  ENCLOSURE_CM_MAX,
  ENCLOSURE_CM_MIN,
  parseEnclosureCmDraft,
} from "@/chamber-3d/components/enclosure/enclosure-cm"
import {
  FELT_POT_COUNT_MAX,
  FELT_POT_PRESETS,
  clampFeltPotCount,
  getFeltPotPreset,
  maxPotsThatFit,
  type FeltPotCount,
  type FeltPotPresetId,
  type PotType,
} from "@/chamber-3d/components/pots/felt-pot-geometry"
import {
  SQUARE_POT_PRESETS,
  getSquarePotPreset,
  maxSquarePotsThatFit,
  type SquarePotPresetId,
} from "@/chamber-3d/components/pots/square-pot-geometry"
import {
  DEFAULT_LIGHT_CEILING_GAP_CM,
  DEFAULT_LIGHT_ORIENTATION_DEG,
  DEFAULT_LIGHT_PRESET_ID,
  LIGHT_CEILING_GAP_MIN_CM,
  LIGHT_ORIENTATIONS_DEG,
  LIGHT_PRESETS,
  clampCeilingGapCm,
  clampLightOrientationDeg,
  getLightPreset,
  listFittingOrientations,
  planLightFit,
  resolveLightOrientationDeg,
  type LightOrientationDeg,
  type LightPresetId,
} from "@/chamber-3d/components/lights/light-geometry"
import {
  DEFAULT_FAN_CEILING_GAP_CM,
  DEFAULT_FAN_ORIENTATION_DEG,
  DEFAULT_FAN_POSITION,
  DEFAULT_FAN_PRESET_ID,
  FAN_CEILING_GAP_MIN_CM,
  FAN_ORIENTATIONS_DEG,
  FAN_POSITIONS,
  FAN_PRESETS,
  clampFanCeilingGapCm,
  clampFanOrientationDeg,
  getFanPreset,
  listFittingFanOrientations,
  planFanFit,
  type FanOrientationDeg,
  type FanPosition,
  type FanPresetId,
  type LightAABB,
} from "@/chamber-3d/components/fans/fan-geometry"
import {
  AppActionRow,
  AppCanvasFrame,
  AppCardBody,
  AppControlSurface,
  AppFieldMetaText,
  AppFormField,
  AppFormGrid,
  AppPage,
  AppPreviewSplit,
  AppSelectTrigger,
} from "@/components/app-chrome"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectValue,
} from "@/components/ui/select"
import { navigate, ROUTES } from "@/lib/routing"

const DEFAULT_WIDTH_CM = 80
const DEFAULT_DEPTH_CM = 80
const DEFAULT_HEIGHT_CM = 160
const DEFAULT_WALL_HEIGHT_CM = 260
const DEFAULT_POT_COUNT: FeltPotCount = 1

/** Composite key encoding pot type + preset id, e.g. "felt/12l". */
type PotKey = `${PotType}/${FeltPotPresetId | SquarePotPresetId}`
const DEFAULT_POT_KEY: PotKey = "felt/12l"

function parsePotKey(key: string): { type: PotType; presetId: FeltPotPresetId | SquarePotPresetId } | null {
  const parts = key.split("/")
  if (parts.length !== 2) return null
  const type = parts[0]
  if (type !== "felt" && type !== "square") return null
  const presetId = parts[1]
  if (!["7l", "11l", "12l", "15l", "19l", "26l", "38l"].includes(presetId)) return null
  return { type: type as PotType, presetId: presetId as FeltPotPresetId | SquarePotPresetId }
}

type CmFieldProps = {
  id: string
  label: string
  valueCm: number
  onValueCmChange: (nextCm: number) => void
  minCm?: number
  maxCm?: number
  end?: React.ReactNode
}

function CmDimensionField({
  id,
  label,
  valueCm,
  onValueCmChange,
  minCm = ENCLOSURE_CM_MIN,
  maxCm = ENCLOSURE_CM_MAX,
  end,
}: CmFieldProps) {
  const [draft, setDraft] = useState(String(valueCm))
  const [syncedCm, setSyncedCm] = useState(valueCm)

  if (valueCm !== syncedCm) {
    setSyncedCm(valueCm)
    setDraft(String(valueCm))
  }

  function commit(): void {
    const parsed = parseEnclosureCmDraft(draft)
    if (parsed === null) {
      setDraft(String(valueCm))
      return
    }
    const next = Math.min(maxCm, Math.max(minCm, Math.round(parsed)))
    onValueCmChange(next)
    setDraft(String(next))
  }

  return (
    <AppFormField label={label} htmlFor={id} end={end}>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={minCm}
        max={maxCm}
        step={1}
        value={draft}
        onChange={(event) => {
          const raw = event.target.value
          setDraft(raw)
          const parsed = parseEnclosureCmDraft(raw)
          if (parsed !== null && parsed >= minCm && parsed <= maxCm) {
            onValueCmChange(Math.round(parsed))
          }
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur()
          }
        }}
      />
    </AppFormField>
  )
}

export function Chamber3dPage() {
  const [widthCm, setWidthCm] = useState(DEFAULT_WIDTH_CM)
  const [depthCm, setDepthCm] = useState(DEFAULT_DEPTH_CM)
  const [heightCm, setHeightCm] = useState(DEFAULT_HEIGHT_CM)
  const [potKey, setPotKey] = useState<PotKey>(DEFAULT_POT_KEY)
  const [potCount, setPotCount] = useState<FeltPotCount>(DEFAULT_POT_COUNT)
  const [lightPresetId, setLightPresetId] = useState<LightPresetId>(DEFAULT_LIGHT_PRESET_ID)
  const [lightOrientationDeg, setLightOrientationDeg] =
    useState<LightOrientationDeg>(DEFAULT_LIGHT_ORIENTATION_DEG)
  const [lightCeilingGapCm, setLightCeilingGapCm] = useState(DEFAULT_LIGHT_CEILING_GAP_CM)
  const [lightOn, setLightOn] = useState(true)
  const [fanPresetId, setFanPresetId] = useState<FanPresetId>(DEFAULT_FAN_PRESET_ID)
  const [fanOrientationDeg, setFanOrientationDeg] =
    useState<FanOrientationDeg>(DEFAULT_FAN_ORIENTATION_DEG)
  const [fanCeilingGapCm, setFanCeilingGapCm] = useState(DEFAULT_FAN_CEILING_GAP_CM)
  const [fanPosition, setFanPosition] = useState<FanPosition>(DEFAULT_FAN_POSITION)
  const [roomLayout, setRoomLayout] = useState<RoomLayout>("flat")
  const [wallHeightCm, setWallHeightCm] = useState(DEFAULT_WALL_HEIGHT_CM)

  const volumeM3 = useMemo(
    () => (widthCm * depthCm * heightCm) / 1_000_000,
    [widthCm, depthCm, heightCm],
  )

  const potKeyParsed = useMemo(() => {
    const parsed = parsePotKey(potKey)
    if (parsed) return parsed
    // Fallback — guaranteed valid by DEFAULT_POT_KEY constant
    const fallback = parsePotKey(DEFAULT_POT_KEY)
    if (!fallback) throw new Error(`Invalid DEFAULT_POT_KEY: ${DEFAULT_POT_KEY}`)
    return fallback
  }, [potKey])
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

  // ---- Fan and Light placement with dynamic mutual avoidance ----
  const fanPreset = useMemo(() => getFanPreset(fanPresetId), [fanPresetId])

  const baseFanGap = useMemo(
    () => clampFanCeilingGapCm(fanCeilingGapCm, heightCm / 100, fanPreset.bodyDiameterCm, potMaxHeightCm),
    [fanCeilingGapCm, heightCm, fanPreset.bodyDiameterCm, potMaxHeightCm],
  )

  const fanOnlyPlan = useMemo(
    () =>
      planFanFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        fanOrientationDeg,
        baseFanGap,
        null,
        fanPosition,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, fanPreset, fanOrientationDeg, baseFanGap, fanPosition, potMaxHeightCm],
  )

  const baseLightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        lightOrientationDeg,
        clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm, potMaxHeightCm),
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, lightOrientationDeg, lightCeilingGapCm, potMaxHeightCm],
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

  // ---- Light placement with fan-safe gap ----
  const lightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        lightOrientationDeg,
        effectiveLightCeilingGapCm,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, lightPreset, lightOrientationDeg, effectiveLightCeilingGapCm, potMaxHeightCm],
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

  // ---- Fan placement with actual light AABB for horizontal avoidance ----
  const fanPlan = useMemo(
    () =>
      planFanFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        fanOrientationDeg,
        effectiveFanCeilingGapCm,
        lightAABB,
        fanPosition,
        potMaxHeightCm,
      ),
    [widthCm, depthCm, heightCm, fanPreset, fanOrientationDeg, effectiveFanCeilingGapCm, lightAABB, fanPosition, potMaxHeightCm],
  )

  // ---- Derived values for light UI ----
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

  // ---- Derived values for fan UI ----
  const fanFittingOrientations = useMemo(
    () =>
      listFittingFanOrientations(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        effectiveFanCeilingGapCm,
      ),
    [widthCm, depthCm, heightCm, fanPreset, effectiveFanCeilingGapCm],
  )

  const effectiveFanOrientationDeg = useMemo(() => {
    if (fanPreset.form === "none") return fanOrientationDeg
    if (fanFittingOrientations.length === 0) return fanOrientationDeg
    if (fanFittingOrientations.includes(fanOrientationDeg)) return fanOrientationDeg
    return fanFittingOrientations[0]!
  }, [fanPreset.form, fanFittingOrientations, fanOrientationDeg])

  /** Scalone ustawienie pozycji i orientacji wentylatora. */
  type FanPlacementKey = `${FanPosition}/${FanOrientationDeg}`

  const fanPlacementOptions: { key: FanPlacementKey; label: string }[] = []
  for (const pos of FAN_POSITIONS) {
    for (const deg of FAN_ORIENTATIONS_DEG) {
      const posLabel = pos === "rear-left-wall" ? "Lewa" : "Prawa"
      const degLabel = deg === 0 ? "wzdłuż szer." : "wzdłuż głęb."
      const key = `${pos}/${deg}` as FanPlacementKey
      const fits =
        fanPreset.form === "none" || (fanFittingOrientations.includes(deg))
      const label = fits
        ? `${posLabel} · ${degLabel}`
        : `${posLabel} · ${degLabel} (nie mieści)`
      fanPlacementOptions.push({ key, label })
    }
  }

  const currentFanPlacementKey: FanPlacementKey = `${fanPosition}/${effectiveFanOrientationDeg}`

  function parseFanPlacementKey(key: string): { position: FanPosition; orientationDeg: FanOrientationDeg } | null {
    const parts = key.split("/")
    if (parts.length !== 2) return null
    const pos = parts[0]
    if (pos !== "rear-left-wall" && pos !== "rear-right-wall") return null
    const deg = Number(parts[1])
    if (deg !== 0 && deg !== 90) return null
    return { position: pos as FanPosition, orientationDeg: deg as FanOrientationDeg }
  }

  return (
    <AppPage width="wide">
      <AppPreviewSplit
        sidebar={
          <Card>
            <CardHeader>
              <CardTitle>Ustawienia</CardTitle>
              <CardAction>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate(ROUTES.configurator)}
                >
                  Wróć
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent>
              <AppCardBody variant="form">
                <AppControlSurface>
                  <AppFormGrid>
                    <CmDimensionField
                      id="width_cm"
                      label="Szerokość (cm)"
                      valueCm={widthCm}
                      onValueCmChange={setWidthCm}
                    />
                    <CmDimensionField
                      id="depth_cm"
                      label="Głębokość (cm)"
                      valueCm={depthCm}
                      onValueCmChange={setDepthCm}
                    />
                    <CmDimensionField
                      id="height_cm"
                      label="Wysokość (cm)"
                      valueCm={heightCm}
                      onValueCmChange={setHeightCm}
                      maxCm={240}
                    />
                    <AppFormField label="Objętość (m³)" htmlFor="volume_m3">
                      <Input
                        id="volume_m3"
                        type="text"
                        inputMode="decimal"
                        value={volumeM3.toFixed(4)}
                        readOnly
                        disabled
                      />
                    </AppFormField>
                  </AppFormGrid>
                </AppControlSurface>

                <AppControlSurface>
                  <AppFormGrid>
                    <AppFormField label="Donica" htmlFor="pot_size">
                      <Select
                        value={potKey}
                        onValueChange={(value) => setPotKey(value as PotKey)}
                      >
                        <AppSelectTrigger id="pot_size">
                          <SelectValue placeholder="Rozmiar" />
                        </AppSelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectLabel>Okrągła (filcowa)</SelectLabel>
                            {FELT_POT_PRESETS.map((preset) => (
                              <SelectItem key={`felt/${preset.id}`} value={`felt/${preset.id}`}>
                                {preset.volumeL} L · ⌀{preset.diameterCm}×{preset.heightCm}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                          <SelectGroup>
                            <SelectLabel>Kwadratowa (plastikowa)</SelectLabel>
                            {SQUARE_POT_PRESETS.map((preset) => (
                              <SelectItem key={`square/${preset.id}`} value={`square/${preset.id}`}>
                                {preset.volumeL} L · {preset.sideCm}×{preset.sideCm}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <AppFormField
                      label="Liczba"
                      htmlFor="pot_count"
                      end={
                        maxFit === 0 && potCount > 0 ? (
                          <Badge variant="destructive">0/{maxFit}</Badge>
                        ) : (
                          <Badge variant="secondary">
                            {visiblePotCount}/{maxFit}
                          </Badge>
                        )
                      }
                    >
                      <Select
                        value={String(visiblePotCount)}
                        onValueChange={(value) => setPotCount(clampFeltPotCount(Number(value)))}
                      >
                        <AppSelectTrigger id="pot_count">
                          <SelectValue placeholder="Liczba" />
                        </AppSelectTrigger>
                        <SelectContent>
                          {Array.from({ length: FELT_POT_COUNT_MAX + 1 }, (_, n) => {
                            const fits = n <= maxFit
                            return (
                              <SelectItem key={n} value={String(n)} disabled={n > 0 && !fits}>
                                {n === 0 ? "0" : fits ? `${n}` : `${n} (za dużo)`}
                              </SelectItem>
                            )
                          })}
                        </SelectContent>
                      </Select>
                    </AppFormField>
                  </AppFormGrid>
                </AppControlSurface>

                <AppControlSurface>
                  <AppFormGrid>
                    <AppFormField
                      label="Lampa"
                      htmlFor="light_preset"
                      end={
                        lightPreset.form === "none" ? (
                          <Badge variant="outline">off</Badge>
                        ) : lightPlan.fits ? (
                          <Badge variant="secondary">OK</Badge>
                        ) : (
                          <Badge variant="destructive">za duża</Badge>
                        )
                      }
                    >
                      <Select
                        value={lightPresetId}
                        onValueChange={(value) => setLightPresetId(value as LightPresetId)}
                      >
                        <AppSelectTrigger id="light_preset">
                          <SelectValue placeholder="Model" />
                        </AppSelectTrigger>
                        <SelectContent>
                          {LIGHT_PRESETS.map((preset) => (
                            <SelectItem key={preset.id} value={preset.id}>
                              {preset.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <AppFormField label="Obrót" htmlFor="light_orientation">
                      <Select
                        value={String(effectiveLightOrientationDeg)}
                        onValueChange={(value) =>
                          setLightOrientationDeg(clampLightOrientationDeg(Number(value)))
                        }
                        disabled={lightPreset.form === "none"}
                      >
                        <AppSelectTrigger id="light_orientation">
                          <SelectValue placeholder="Obrót" />
                        </AppSelectTrigger>
                        <SelectContent>
                          {LIGHT_ORIENTATIONS_DEG.map((deg) => {
                            const fitsYaw =
                              lightPreset.form === "none" || fittingOrientations.includes(deg)
                            const label = deg === 0 ? "0° · wzdłuż szer." : "90° · wzdłuż głęb."
                            return (
                              <SelectItem
                                key={deg}
                                value={String(deg)}
                                disabled={!fitsYaw && fittingOrientations.length > 0}
                              >
                                {fitsYaw ? label : `${label} (nie mieści)`}
                              </SelectItem>
                            )
                          })}
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <CmDimensionField
                      id="light_ceiling_gap_cm"
                      label="Od sufitu (cm)"
                      valueCm={effectiveLightCeilingGapCm}
                      onValueCmChange={(next) => {
                        let nextLight = next
                        if (hasHorizontalOverlap && fanPreset.form !== "none") {
                          const minLight = FAN_CEILING_GAP_MIN_CM + fanPreset.bodyDiameterCm + 2
                          nextLight = Math.max(nextLight, minLight)
                        }
                        nextLight = clampCeilingGapCm(nextLight, heightCm / 100, lightPreset.heightCm, potMaxHeightCm)
                        setLightCeilingGapCm(nextLight)

                        if (hasHorizontalOverlap && fanPreset.form !== "none") {
                          const maxFan = nextLight - fanPreset.bodyDiameterCm - 2
                          if (fanCeilingGapCm > maxFan) {
                            setFanCeilingGapCm(maxFan)
                          }
                        }
                      }}
                      minCm={
                        hasHorizontalOverlap && fanPreset.form !== "none"
                          ? Math.ceil(FAN_CEILING_GAP_MIN_CM + fanPreset.bodyDiameterCm + 2)
                          : LIGHT_CEILING_GAP_MIN_CM
                      }
                      maxCm={lightPreset.form === "none" ? LIGHT_CEILING_GAP_MIN_CM : lightPlan.maxCeilingGapCm}
                      end={
                        <AppFieldMetaText>
                          max {lightPreset.form === "none" ? "—" : `${lightPlan.maxCeilingGapCm} cm`}
                        </AppFieldMetaText>
                      }
                    />

                    <AppFormField label="Świeci" htmlFor="light_on">
                      <Select
                        value={lightOn ? "on" : "off"}
                        onValueChange={(value) => setLightOn(value === "on")}
                        disabled={lightPreset.form === "none" || !lightPlan.fits}
                      >
                        <AppSelectTrigger id="light_on">
                          <SelectValue placeholder="Stan" />
                        </AppSelectTrigger>
                        <SelectContent>
                          <SelectItem value="on">Włączona</SelectItem>
                          <SelectItem value="off">Wyłączona</SelectItem>
                        </SelectContent>
                      </Select>
                    </AppFormField>
                  </AppFormGrid>
                </AppControlSurface>

                <AppControlSurface>
                  <AppFormGrid>
                    <AppFormField
                      label="Wentylator"
                      htmlFor="fan_preset"
                      end={
                        fanPreset.form === "none" ? (
                          <Badge variant="outline">off</Badge>
                        ) : fanPlan.fits ? (
                          <Badge variant="secondary">OK</Badge>
                        ) : (
                          <Badge variant="destructive">{fanPlan.reason ?? "koliduje"}</Badge>
                        )
                      }
                    >
                      <Select
                        value={fanPresetId}
                        onValueChange={(value) => setFanPresetId(value as FanPresetId)}
                      >
                        <AppSelectTrigger id="fan_preset">
                          <SelectValue placeholder="Model" />
                        </AppSelectTrigger>
                        <SelectContent>
                          {FAN_PRESETS.map((preset) => (
                            <SelectItem key={preset.id} value={preset.id}>
                              {preset.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <AppFormField label="Umiejscowienie" htmlFor="fan_placement">
                      <Select
                        value={currentFanPlacementKey}
                        onValueChange={(value) => {
                          const parsed = parseFanPlacementKey(value)
                          if (!parsed) return
                          setFanPosition(parsed.position)
                          setFanOrientationDeg(clampFanOrientationDeg(parsed.orientationDeg))
                        }}
                        disabled={fanPreset.form === "none"}
                      >
                        <AppSelectTrigger id="fan_placement">
                          <SelectValue placeholder="Umiejscowienie" />
                        </AppSelectTrigger>
                        <SelectContent>
                          {fanPlacementOptions.map((opt) => {
                            const parsed = parseFanPlacementKey(opt.key)
                            const deg = parsed?.orientationDeg
                            const fits =
                              fanPreset.form === "none" ||
                              (deg !== undefined && fanFittingOrientations.includes(deg))
                            return (
                              <SelectItem key={opt.key} value={opt.key} disabled={!fits}>
                                {opt.label}
                              </SelectItem>
                            )
                          })}
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <CmDimensionField
                      id="fan_ceiling_gap_cm"
                      label="Od sufitu (cm)"
                      valueCm={effectiveFanCeilingGapCm}
                      onValueCmChange={(next) => {
                        let nextFan = next
                        if (hasHorizontalOverlap && lightPreset.form !== "none") {
                          const maxFan = baseLightPlan.maxCeilingGapCm - fanPreset.bodyDiameterCm - 2
                          nextFan = Math.min(nextFan, maxFan)
                        }
                        nextFan = clampFanCeilingGapCm(nextFan, heightCm / 100, fanPreset.bodyDiameterCm, potMaxHeightCm)
                        setFanCeilingGapCm(nextFan)

                        if (hasHorizontalOverlap && lightPreset.form !== "none") {
                          const minLight = nextFan + fanPreset.bodyDiameterCm + 2
                          if (lightCeilingGapCm < minLight) {
                            setLightCeilingGapCm(minLight)
                          }
                        }
                      }}
                      minCm={FAN_CEILING_GAP_MIN_CM}
                      maxCm={
                        fanPreset.form === "none"
                          ? FAN_CEILING_GAP_MIN_CM
                          : Math.min(
                              fanPlan.maxCeilingGapCm,
                              hasHorizontalOverlap && lightPreset.form !== "none"
                                ? Math.floor(baseLightPlan.maxCeilingGapCm - fanPreset.bodyDiameterCm - 2)
                                : fanPlan.maxCeilingGapCm
                            )
                      }
                      end={
                        <AppFieldMetaText>
                          max {fanPreset.form === "none" ? "—" : `${fanPlan.maxCeilingGapCm} cm`}
                        </AppFieldMetaText>
                      }
                    />
                  </AppFormGrid>
                </AppControlSurface>

                <AppControlSurface>
                  <AppFormGrid>
                    <AppFormField label="Tło sceny" htmlFor="room_layout">
                      <Select
                        value={roomLayout}
                        onValueChange={(value) => setRoomLayout(value as RoomLayout)}
                      >
                        <AppSelectTrigger id="room_layout">
                          <SelectValue placeholder="Tło" />
                        </AppSelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Studio (bez ścian)</SelectItem>
                          <SelectItem value="flat">Przy ścianie</SelectItem>
                          <SelectItem value="corner">W rogu</SelectItem>
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <CmDimensionField
                      id="wall_height_cm"
                      label="Wys. ściany (cm)"
                      valueCm={wallHeightCm}
                      onValueCmChange={setWallHeightCm}
                      maxCm={260}
                    />
                  </AppFormGrid>
                </AppControlSurface>

                <AppActionRow align="end">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setWidthCm(DEFAULT_WIDTH_CM)
                      setDepthCm(DEFAULT_DEPTH_CM)
                      setHeightCm(DEFAULT_HEIGHT_CM)
                      setPotKey(DEFAULT_POT_KEY)
                      setPotCount(DEFAULT_POT_COUNT)
                      setLightPresetId(DEFAULT_LIGHT_PRESET_ID)
                      setLightOrientationDeg(DEFAULT_LIGHT_ORIENTATION_DEG)
                      setLightCeilingGapCm(DEFAULT_LIGHT_CEILING_GAP_CM)
                      setLightOn(true)
                      setFanPresetId(DEFAULT_FAN_PRESET_ID)
                      setFanOrientationDeg(DEFAULT_FAN_ORIENTATION_DEG)
                      setFanCeilingGapCm(DEFAULT_FAN_CEILING_GAP_CM)
                      setFanPosition(DEFAULT_FAN_POSITION)
                      setWallHeightCm(DEFAULT_WALL_HEIGHT_CM)
                    }}
                  >
                    Reset
                  </Button>
                </AppActionRow>
              </AppCardBody>
            </CardContent>
          </Card>
        }
        main={
          <AppCanvasFrame>
            <ChamberPerformanceProvider>
              <PerformanceOverlay />
              <ChamberCanvas
                widthCm={widthCm}
                depthCm={depthCm}
                heightCm={heightCm}
                potType={potType}
                potPresetId={potPresetId}
                potCount={visiblePotCount}
                lightPresetId={lightPresetId}
                lightOrientationDeg={effectiveLightOrientationDeg}
                lightCeilingGapCm={effectiveLightCeilingGapCm}
                lightOn={lightOn && lightPlan.fits}
                fanPresetId={fanPresetId}
                fanOrientationDeg={effectiveFanOrientationDeg}
                fanCeilingGapCm={effectiveFanCeilingGapCm}
                fanPosition={fanPosition}
                roomLayout={roomLayout}
                wallHeightCm={wallHeightCm}
              />
            </ChamberPerformanceProvider>
          </AppCanvasFrame>
        }
      />
    </AppPage>
  )
}
