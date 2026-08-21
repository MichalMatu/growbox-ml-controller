import {
  AppControlSurface,
  AppFieldMetaText,
  AppFormField,
  AppFormGrid,
  AppSelectTrigger,
} from "@/components/app-chrome"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select"
import {
  FAN_CEILING_GAP_MIN_CM,
  FAN_ORIENTATIONS_DEG,
  FAN_POSITIONS,
  FAN_PRESETS,
  clampFanCeilingGapCm,
  clampFanOrientationDeg,
  type FanOrientationDeg,
  type FanPosition,
  type FanPresetId,
  type FanPreset,
  type FanFitResult,
} from "@/chamber-3d/components/fans/fan-geometry"
import { type LightPreset, type LightFitResult } from "@/chamber-3d/components/lights/light-geometry"
import { CmDimensionField } from "./cm-dimension-field"

type FansFormProps = {
  fanPresetId: FanPresetId
  setFanPresetId: (id: FanPresetId) => void
  setFanOrientationDeg: (deg: FanOrientationDeg) => void
  setFanCeilingGapCm: (cm: number) => void
  fanPosition: FanPosition
  setFanPosition: (pos: FanPosition) => void
  effectiveFanOrientationDeg: number
  effectiveFanCeilingGapCm: number
  fanPreset: FanPreset
  fanPlan: FanFitResult
  fanFittingOrientations: number[]
  hasHorizontalOverlap: boolean
  lightPreset: LightPreset
  lightCeilingGapCm: number
  setLightCeilingGapCm: (cm: number) => void
  baseLightPlan: LightFitResult
  heightCm: number
  potMaxHeightCm: number
}

type FanPlacementKey = `${FanPosition}/${FanOrientationDeg}`

export function FansForm({
  fanPresetId,
  setFanPresetId,
  setFanOrientationDeg,
  setFanCeilingGapCm,
  fanPosition,
  setFanPosition,
  effectiveFanOrientationDeg,
  effectiveFanCeilingGapCm,
  fanPreset,
  fanPlan,
  fanFittingOrientations,
  hasHorizontalOverlap,
  lightPreset,
  lightCeilingGapCm,
  setLightCeilingGapCm,
  baseLightPlan,
  heightCm,
  potMaxHeightCm,
}: FansFormProps) {
  const fanPlacementOptions: { key: FanPlacementKey; label: string }[] = []
  for (const pos of FAN_POSITIONS) {
    for (const deg of FAN_ORIENTATIONS_DEG as FanOrientationDeg[]) {
      const posLabel = pos === "rear-left-wall" ? "Lewa" : "Prawa"
      const degLabel = deg === 0 ? "wzdłuż szer." : "wzdłuż głęb."
      const keyStr = `${pos}/${deg}`
      const key = keyStr as unknown as FanPlacementKey
      const fits = fanPreset.form === "none" || fanFittingOrientations.includes(deg)
      const label = fits ? `${posLabel} · ${degLabel}` : `${posLabel} · ${degLabel} (nie mieści)`
      fanPlacementOptions.push({ key, label })
    }
  }

  const currentFanPlacementKey = `${fanPosition}/${effectiveFanOrientationDeg}` as unknown as FanPlacementKey

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
  )
}
