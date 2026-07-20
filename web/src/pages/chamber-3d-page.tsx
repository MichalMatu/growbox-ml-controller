import { useMemo, useState } from "react"

import { ChamberCanvas } from "@/chamber-3d/chamber-scene"
import { ChamberPerformanceProvider } from "@/chamber-3d/performance-context"
import { PerformanceOverlay } from "@/chamber-3d/performance-overlay"
import { type RoomLayout } from "@/chamber-3d/room"
import {
  ENCLOSURE_CM_MAX,
  ENCLOSURE_CM_MIN,
  parseEnclosureCmDraft,
} from "@/chamber-3d/enclosure-cm"
import {
  DEFAULT_FELT_POT_PRESET_ID,
  FELT_POT_COUNT_MAX,
  FELT_POT_PRESETS,
  clampFeltPotCount,
  getFeltPotPreset,
  maxPotsThatFit,
  type FeltPotCount,
  type FeltPotPresetId,
} from "@/chamber-3d/felt-pot-geometry"
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
} from "@/chamber-3d/light-geometry"
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
  SelectItem,
  SelectValue,
} from "@/components/ui/select"
import { navigate, ROUTES } from "@/lib/routing"

const DEFAULT_WIDTH_CM = 80
const DEFAULT_DEPTH_CM = 80
const DEFAULT_HEIGHT_CM = 160
const DEFAULT_POT_COUNT: FeltPotCount = 1

type CmFieldProps = {
  id: string
  label: string
  valueCm: number
  onValueCmChange: (nextCm: number) => void
  minCm?: number
  maxCm?: number
}

/**
 * Draft string while typing; clamp only on blur / Enter.
 * Live 3D updates only when the draft is already within min–max.
 */
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

/**
 * Isolated R3F playground. DOM chrome only via app-chrome + shadcn.
 * No freehand Tailwind in this file (enforced by lint/tests).
 */
export function Chamber3dPage() {
  const [widthCm, setWidthCm] = useState(DEFAULT_WIDTH_CM)
  const [depthCm, setDepthCm] = useState(DEFAULT_DEPTH_CM)
  const [heightCm, setHeightCm] = useState(DEFAULT_HEIGHT_CM)
  const [potPresetId, setPotPresetId] = useState<FeltPotPresetId>(
    DEFAULT_FELT_POT_PRESET_ID,
  )
  const [potCount, setPotCount] = useState<FeltPotCount>(DEFAULT_POT_COUNT)
  const [lightPresetId, setLightPresetId] = useState<LightPresetId>(
    DEFAULT_LIGHT_PRESET_ID,
  )
  const [lightOrientationDeg, setLightOrientationDeg] =
    useState<LightOrientationDeg>(DEFAULT_LIGHT_ORIENTATION_DEG)
  const [lightCeilingGapCm, setLightCeilingGapCm] = useState(
    DEFAULT_LIGHT_CEILING_GAP_CM,
  )
  const [lightOn, setLightOn] = useState(true)
  const [roomLayout, setRoomLayout] = useState<RoomLayout>("none")

  const volumeM3 = useMemo(
    () => (widthCm * depthCm * heightCm) / 1_000_000,
    [widthCm, depthCm, heightCm],
  )

  const potPreset = useMemo(() => getFeltPotPreset(potPresetId), [potPresetId])
  const footprint = useMemo(
    () => ({ diameterCm: potPreset.diameterCm, heightCm: potPreset.heightCm }),
    [potPreset.diameterCm, potPreset.heightCm],
  )

  const maxFit = useMemo(
    () =>
      maxPotsThatFit(widthCm / 100, depthCm / 100, heightCm / 100, footprint),
    [widthCm, depthCm, heightCm, footprint],
  )

  /** Desired count clamped to what currently fits (keeps higher intent when tent grows). */
  const visiblePotCount = clampFeltPotCount(Math.min(potCount, maxFit))

  const lightPreset = useMemo(
    () => getLightPreset(lightPresetId),
    [lightPresetId],
  )

  /** Derived clamp — no setState during render when tent/fixture shrinks. */
  const effectiveCeilingGapCm = useMemo(
    () =>
      clampCeilingGapCm(
        lightCeilingGapCm,
        heightCm / 100,
        lightPreset.heightCm,
      ),
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

  /** If current yaw does not fit but another does, snap to a valid one. */
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
    [
      widthCm,
      depthCm,
      heightCm,
      lightPreset,
      lightOrientationDeg,
      effectiveCeilingGapCm,
    ],
  )

  const lightPlan = useMemo(
    () =>
      planLightFit(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        lightPreset,
        effectiveLightOrientationDeg,
        effectiveCeilingGapCm,
      ),
    [
      widthCm,
      depthCm,
      heightCm,
      lightPreset,
      effectiveLightOrientationDeg,
      effectiveCeilingGapCm,
    ],
  )

  const lightSizeLabel =
    lightPreset.form === "none"
      ? "—"
      : `${lightPreset.lengthCm}×${lightPreset.widthCm}×${lightPreset.heightCm} cm`

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
                      value={potPresetId}
                      onValueChange={(value) => {
                        setPotPresetId(value as FeltPotPresetId)
                      }}
                    >
                      <AppSelectTrigger id="pot_size">
                        <SelectValue placeholder="Rozmiar" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {FELT_POT_PRESETS.map((preset) => (
                          <SelectItem key={preset.id} value={preset.id}>
                            {preset.volumeL} L · {preset.diameterCm}×
                            {preset.heightCm}
                          </SelectItem>
                        ))}
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
                      onValueChange={(value) => {
                        setPotCount(clampFeltPotCount(Number(value)))
                      }}
                    >
                      <AppSelectTrigger id="pot_count">
                        <SelectValue placeholder="Liczba" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {Array.from({ length: FELT_POT_COUNT_MAX + 1 }, (_, n) => {
                          const fits = n <= maxFit
                          return (
                            <SelectItem
                              key={n}
                              value={String(n)}
                              disabled={n > 0 && !fits}
                            >
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
                      onValueChange={(value) => {
                        setLightPresetId(value as LightPresetId)
                      }}
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
                    <Input
                      id="light_size"
                      type="text"
                      value={lightSizeLabel}
                      readOnly
                      disabled
                    />
                  </AppFormField>

                  <AppFormField label="Obrót" htmlFor="light_orientation">
                    <Select
                      value={String(effectiveLightOrientationDeg)}
                      onValueChange={(value) => {
                        setLightOrientationDeg(
                          clampLightOrientationDeg(Number(value)),
                        )
                      }}
                      disabled={lightPreset.form === "none"}
                    >
                      <AppSelectTrigger id="light_orientation">
                        <SelectValue placeholder="Obrót" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {LIGHT_ORIENTATIONS_DEG.map((deg) => {
                          const fitsYaw =
                            lightPreset.form === "none" ||
                            fittingOrientations.includes(deg)
                          const label =
                            deg === 0
                              ? "0° · wzdłuż szer."
                              : "90° · wzdłuż głęb."
                          return (
                            <SelectItem
                              key={deg}
                              value={String(deg)}
                              disabled={!fitsYaw && fittingOrientations.length > 0}
                            >
                              {fitsYaw
                                ? label
                                : `${label} (nie mieści)`}
                            </SelectItem>
                          )
                        })}
                      </SelectContent>
                    </Select>
                  </AppFormField>

                  <CmDimensionField
                    id="light_ceiling_gap_cm"
                    label="Od sufitu (cm)"
                    valueCm={effectiveCeilingGapCm}
                    onValueCmChange={(next) => {
                      setLightCeilingGapCm(
                        clampCeilingGapCm(
                          next,
                          heightCm / 100,
                          lightPreset.heightCm,
                        ),
                      )
                    }}
                    minCm={LIGHT_CEILING_GAP_MIN_CM}
                    maxCm={Math.max(
                      LIGHT_CEILING_GAP_MIN_CM,
                      lightPlan.maxCeilingGapCm,
                    )}
                  />

                  <AppFormField label="Świeci" htmlFor="light_on">
                    <Select
                      value={lightOn ? "on" : "off"}
                      onValueChange={(value) => {
                        setLightOn(value === "on")
                      }}
                      disabled={
                        lightPreset.form === "none" || !lightPlan.fits
                      }
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
                      value={
                        lightPreset.form === "none"
                          ? "—"
                          : `${lightPlan.maxCeilingGapCm} cm`
                      }
                      readOnly
                      disabled
                    />
                  </AppFormField>

                  <AppFormField label="Tło sceny" htmlFor="room_layout">
                    <Select
                      value={roomLayout}
                      onValueChange={(value) => {
                        setRoomLayout(value as RoomLayout)
                      }}
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
                </AppFormGrid>

                <AppActionRow align="end">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setWidthCm(DEFAULT_WIDTH_CM)
                      setDepthCm(DEFAULT_DEPTH_CM)
                      setHeightCm(DEFAULT_HEIGHT_CM)
                      setPotPresetId(DEFAULT_FELT_POT_PRESET_ID)
                      setPotCount(DEFAULT_POT_COUNT)
                      setLightPresetId(DEFAULT_LIGHT_PRESET_ID)
                      setLightOrientationDeg(DEFAULT_LIGHT_ORIENTATION_DEG)
                      setLightCeilingGapCm(DEFAULT_LIGHT_CEILING_GAP_CM)
                      setLightOn(true)
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
                potPresetId={potPresetId}
                potCount={visiblePotCount}
                lightPresetId={lightPresetId}
                lightOrientationDeg={effectiveLightOrientationDeg}
                lightCeilingGapCm={effectiveCeilingGapCm}
                lightOn={lightOn && lightPlan.fits}
                roomLayout={roomLayout}
              />
            </ChamberPerformanceProvider>
          </AppCanvasFrame>
        }
      />
    </AppPage>
  )
}
