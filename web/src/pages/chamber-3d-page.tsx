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
  computeLightCeilingGapForFan,
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
}

function CmDimensionField({
  id,
  label,
  valueCm,
  onValueCmChange,
  minCm = ENCLOSURE_CM_MIN,
  maxCm = ENCLOSURE_CM_MAX,
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
    <AppFormField label={label} htmlFor={id}>
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

  const potKeyParsed = useMemo(() => parsePotKey(potKey) ?? parsePotKey(DEFAULT_POT_KEY)!, [potKey])
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

  const lightPreset = useMemo(() => getLightPreset(lightPresetId), [lightPresetId])

  // ---- Fan logic (computed first, independent of light gap) ----
  const fanPreset = useMemo(() => getFanPreset(fanPresetId), [fanPresetId])

  const effectiveFanCeilingGapCm = useMemo(
    () => clampFanCeilingGapCm(fanCeilingGapCm, heightCm / 100, fanPreset.bodyDiameterCm),
    [fanCeilingGapCm, heightCm, fanPreset.bodyDiameterCm],
  )

  const fanOnlyPlan = useMemo(
    () =>
      planFanFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        fanPreset,
        fanOrientationDeg,
        effectiveFanCeilingGapCm,
        null,
        fanPosition,
      ),
    [widthCm, depthCm, heightCm, fanPreset, fanOrientationDeg, effectiveFanCeilingGapCm, fanPosition],
  )

  // Max light ceiling gap that avoids vertical collision with fan
  const lightGapForFanConstraint = useMemo(
    () =>
      computeLightCeilingGapForFan(
        heightCm / 100,
        fanOnlyPlan.placement,
        lightPreset.heightCm,
      ),
    [heightCm, fanOnlyPlan.placement, lightPreset.heightCm],
  )

  // Light gap clamped to avoid fan, then used for light placement.
  // Larger gap = lamp hangs lower, so we need Math.MAX to push it below the fan.
  const lightGapWithFanConstraint = useMemo(() => {
    const base = clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm)
    if (lightGapForFanConstraint != null) {
      return Math.max(base, lightGapForFanConstraint)
    }
    return base
  }, [lightCeilingGapCm, heightCm, lightPreset.heightCm, lightGapForFanConstraint])

  const lightFanCollision = useMemo(() => {
    if (lightGapForFanConstraint == null || fanPreset.form === "none") return false
    const userGap = clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm)
    // User wants lamp closer to ceiling than fan allows → collision
    return userGap < lightGapForFanConstraint
  }, [lightCeilingGapCm, heightCm, lightPreset.heightCm, lightGapForFanConstraint, fanPreset.form])

  // ---- Light placement with fan-safe gap ----
  const lightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        lightOrientationDeg,
        lightGapWithFanConstraint,
      ),
    [widthCm, depthCm, heightCm, lightPreset, lightOrientationDeg, lightGapWithFanConstraint],
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
      ),
    [widthCm, depthCm, heightCm, fanPreset, fanOrientationDeg, effectiveFanCeilingGapCm, lightAABB, fanPosition],
  )

  // ---- Derived values for light UI ----
  const effectiveCeilingGapCm = useMemo(
    () => clampCeilingGapCm(lightCeilingGapCm, heightCm / 100, lightPreset.heightCm),
    [lightCeilingGapCm, heightCm, lightPreset.heightCm],
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

  const lightSizeLabel =
    lightPreset.form === "none"
      ? "—"
      : `${lightPreset.lengthCm}×${lightPreset.widthCm}×${lightPreset.heightCm} cm`

  const fanSizeLabel =
    fanPreset.form === "none"
      ? "—"
      : `Ø${fanPreset.ductDiameterCm} · ${fanPreset.totalLengthCm} cm`

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

                  <AppFormField label="Gabaryt" htmlFor="light_size">
                    <Input id="light_size" type="text" value={lightSizeLabel} readOnly disabled />
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

                  <AppFormField
                    label="Od sufitu (cm)"
                    htmlFor="light_ceiling_gap_cm"
                    end={
                      lightFanCollision && fanPreset.form !== "none" ? (
                        <Badge variant="destructive">kolizja z wentylatorem</Badge>
                      ) : null
                    }
                  >
                    <Input
                      id="light_ceiling_gap_cm"
                      type="number"
                      inputMode="numeric"
                      min={LIGHT_CEILING_GAP_MIN_CM}
                      max={Math.max(LIGHT_CEILING_GAP_MIN_CM, lightPlan.maxCeilingGapCm)}
                      step={1}
                      value={effectiveCeilingGapCm}
                      onChange={(event) => {
                        const raw = event.target.value
                        const parsed = parseEnclosureCmDraft(raw)
                        if (parsed !== null) {
                          setLightCeilingGapCm(
                            clampCeilingGapCm(parsed, heightCm / 100, lightPreset.heightCm),
                          )
                        }
                      }}
                    />
                  </AppFormField>

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

                  <AppFormField label="Max od sufitu" htmlFor="light_gap_max">
                    <Input
                      id="light_gap_max"
                      type="text"
                      value={lightPreset.form === "none" ? "—" : `${lightPlan.maxCeilingGapCm} cm`}
                      readOnly
                      disabled
                    />
                  </AppFormField>

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

                  <AppFormField label="Gabaryt" htmlFor="fan_size">
                    <Input id="fan_size" type="text" value={fanSizeLabel} readOnly disabled />
                  </AppFormField>

                  <AppFormField label="Obrót" htmlFor="fan_orientation">
                    <Select
                      value={String(effectiveFanOrientationDeg)}
                      onValueChange={(value) =>
                        setFanOrientationDeg(clampFanOrientationDeg(Number(value)))
                      }
                      disabled={fanPreset.form === "none"}
                    >
                      <AppSelectTrigger id="fan_orientation">
                        <SelectValue placeholder="Obrót" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {FAN_ORIENTATIONS_DEG.map((deg) => {
                          const fitsYaw =
                            fanPreset.form === "none" || fanFittingOrientations.includes(deg)
                          const label = deg === 0 ? "0° · wzdłuż szer." : "90° · wzdłuż głęb."
                          return (
                            <SelectItem
                              key={deg}
                              value={String(deg)}
                              disabled={!fitsYaw && fanFittingOrientations.length > 0}
                            >
                              {fitsYaw ? label : `${label} (nie mieści)`}
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
                      setFanCeilingGapCm(
                        clampFanCeilingGapCm(next, heightCm / 100, fanPreset.bodyDiameterCm),
                      )
                    }}
                    minCm={FAN_CEILING_GAP_MIN_CM}
                    maxCm={Math.max(FAN_CEILING_GAP_MIN_CM, fanPlan.maxCeilingGapCm)}
                  />

                  <AppFormField label="Max od sufitu" htmlFor="fan_gap_max">
                    <Input
                      id="fan_gap_max"
                      type="text"
                      value={fanPreset.form === "none" ? "—" : `${fanPlan.maxCeilingGapCm} cm`}
                      readOnly
                      disabled
                    />
                  </AppFormField>

                  <AppFormField label="Pozycja" htmlFor="fan_position">
                    <Select
                      value={fanPosition}
                      onValueChange={(value) => setFanPosition(value as FanPosition)}
                      disabled={fanPreset.form === "none"}
                    >
                      <AppSelectTrigger id="fan_position">
                        <SelectValue placeholder="Pozycja" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {FAN_POSITIONS.map((pos) => (
                          <SelectItem key={pos} value={pos}>
                            {pos === "rear-left-wall"
                              ? "Lewa ściana tył"
                              : pos === "rear-right-wall"
                                ? "Prawa ściana tył"
                                : pos === "rear-wall-left"
                                  ? "Tylna lewa"
                                  : "Tylna prawa"}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </AppFormField>

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
                lightCeilingGapCm={lightGapWithFanConstraint}
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
