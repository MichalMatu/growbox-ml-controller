import { useMemo, useState } from "react"

import { ChamberScene } from "@/chamber-3d/chamber-scene"
import {
  commitEnclosureCm,
  ENCLOSURE_CM_MAX,
  ENCLOSURE_CM_MIN,
  isLiveEnclosureCm,
  parseEnclosureCmDraft,
} from "@/chamber-3d/enclosure-cm"
import {
  DEFAULT_FELT_POT_PRESET_ID,
  FELT_POT_COUNT_MAX,
  FELT_POT_PRESETS,
  clampFeltPotCount,
  getFeltPotPreset,
  maxPotsThatFit,
  planFeltPotLayout,
  type FeltPotCount,
  type FeltPotPresetId,
} from "@/chamber-3d/felt-pot-geometry"
import {
  AppActionRow,
  AppCanvasFrame,
  AppCardBody,
  AppFormField,
  AppMutedText,
  AppPage,
  AppPageHeader,
  AppPreviewSplit,
  AppSelectTrigger,
  AppStack,
} from "@/components/app-chrome"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
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
}

/**
 * Draft string while typing; clamp only on blur / Enter.
 * Live 3D updates only when the draft is already within min–max.
 */
function CmDimensionField({ id, label, valueCm, onValueCmChange }: CmFieldProps) {
  const [draft, setDraft] = useState(String(valueCm))
  const [syncedCm, setSyncedCm] = useState(valueCm)

  if (valueCm !== syncedCm) {
    setSyncedCm(valueCm)
    setDraft(String(valueCm))
  }

  function commit(): void {
    const next = commitEnclosureCm(draft, valueCm)
    onValueCmChange(next)
    setDraft(String(next))
  }

  return (
    <AppFormField label={label} htmlFor={id}>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={ENCLOSURE_CM_MIN}
        max={ENCLOSURE_CM_MAX}
        step={1}
        value={draft}
        onChange={(event) => {
          const raw = event.target.value
          setDraft(raw)
          const parsed = parseEnclosureCmDraft(raw)
          if (parsed !== null && isLiveEnclosureCm(parsed)) {
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

  const potPlan = useMemo(
    () =>
      planFeltPotLayout(
        widthCm / 100,
        depthCm / 100,
        heightCm / 100,
        footprint,
        visiblePotCount,
      ),
    [widthCm, depthCm, heightCm, footprint, visiblePotCount],
  )

  const potAspect = (potPreset.diameterCm / potPreset.heightCm).toFixed(2)

  return (
    <AppPage width="wide">
      <AppPageHeader
        title="Podgląd komory 3D"
        badges={
          <>
            <Badge variant="secondary">R3F playground</Badge>
            <Badge variant="outline">oddzielone od konfiguratora</Badge>
          </>
        }
        actions={
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(ROUTES.configurator)}
          >
            Wróć do konfiguratora
          </Button>
        }
      />

      <AppPreviewSplit
        sidebar={
          <AppStack gap="lg">
            <Card>
              <CardHeader>
                <CardTitle>Wymiary komory</CardTitle>
              </CardHeader>
              <CardContent>
                <AppCardBody variant="form">
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
                  <AppMutedText>Objętość: {volumeM3.toFixed(4)} m³</AppMutedText>
                </AppCardBody>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Donice filcowe</CardTitle>
              </CardHeader>
              <CardContent>
                <AppCardBody variant="form">
                  <AppFormField label="Rozmiar donicy" htmlFor="pot_size">
                    <Select
                      value={potPresetId}
                      onValueChange={(value) => {
                        setPotPresetId(value as FeltPotPresetId)
                      }}
                    >
                      <AppSelectTrigger id="pot_size">
                        <SelectValue placeholder="Wybierz rozmiar" />
                      </AppSelectTrigger>
                      <SelectContent>
                        {FELT_POT_PRESETS.map((preset) => (
                          <SelectItem key={preset.id} value={preset.id}>
                            {preset.label} · Ø{preset.diameterCm}×H{preset.heightCm} cm
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </AppFormField>

                  <AppFormField label="Liczba donic" htmlFor="pot_count">
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
                              {n === 0
                                ? "0 — ukryj"
                                : fits
                                  ? `${n}`
                                  : `${n} — nie mieści się`}
                            </SelectItem>
                          )
                        })}
                      </SelectContent>
                    </Select>
                  </AppFormField>

                  <AppMutedText>
                    Ø {potPreset.diameterCm} cm × H {potPreset.heightCm} cm · D/H ={" "}
                    {potAspect} · {potPreset.volumeL} L
                  </AppMutedText>
                  <AppMutedText>
                    Podłoga użyteczna ≈ {potPlan.usableWidthCm.toFixed(0)}×
                    {potPlan.usableDepthCm.toFixed(0)} cm · max mieści się: {maxFit}
                  </AppMutedText>

                  {visiblePotCount === 0 && potCount === 0 ? (
                    <Badge variant="outline">Donice ukryte</Badge>
                  ) : maxFit === 0 ? (
                    <Badge variant="destructive">
                      Nie mieści się (Ø lub wysokość)
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      Pokazano {potPlan.fittedCount} · max {maxFit}
                    </Badge>
                  )}

                  <AppActionRow>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => {
                        setWidthCm(DEFAULT_WIDTH_CM)
                        setDepthCm(DEFAULT_DEPTH_CM)
                        setHeightCm(DEFAULT_HEIGHT_CM)
                        setPotPresetId(DEFAULT_FELT_POT_PRESET_ID)
                        setPotCount(DEFAULT_POT_COUNT)
                      }}
                    >
                      Reset
                    </Button>
                  </AppActionRow>
                </AppCardBody>
              </CardContent>
            </Card>
          </AppStack>
        }
        main={
          <AppCanvasFrame>
            <ChamberScene
              widthCm={widthCm}
              depthCm={depthCm}
              heightCm={heightCm}
              potPresetId={potPresetId}
              potCount={visiblePotCount}
            />
          </AppCanvasFrame>
        }
      />
    </AppPage>
  )
}
