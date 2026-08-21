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
  LIGHT_CEILING_GAP_MIN_CM,
  LIGHT_ORIENTATIONS_DEG,
  LIGHT_PRESETS,
  clampCeilingGapCm,
  clampLightOrientationDeg,
  type LightOrientationDeg,
  type LightPresetId,
  type LightPreset,
  type LightFitResult,
} from "@/chamber-3d/components/lights/light-geometry"
import { FAN_CEILING_GAP_MIN_CM, type FanPreset } from "@/chamber-3d/components/fans/fan-geometry"
import { CmDimensionField } from "./cm-dimension-field"

type LightsFormProps = {
  lightPresetId: LightPresetId
  setLightPresetId: (id: LightPresetId) => void
  setLightOrientationDeg: (deg: LightOrientationDeg) => void
  setLightCeilingGapCm: (cm: number) => void
  lightOn: boolean
  setLightOn: (on: boolean) => void
  effectiveLightOrientationDeg: number
  effectiveLightCeilingGapCm: number
  lightPreset: LightPreset
  lightPlan: LightFitResult
  fittingOrientations: number[]
  hasHorizontalOverlap: boolean
  fanPreset: FanPreset
  fanCeilingGapCm: number
  setFanCeilingGapCm: (cm: number) => void
  heightCm: number
  potMaxHeightCm: number
}

export function LightsForm({
  lightPresetId,
  setLightPresetId,
  setLightOrientationDeg,
  setLightCeilingGapCm,
  lightOn,
  setLightOn,
  effectiveLightOrientationDeg,
  effectiveLightCeilingGapCm,
  lightPreset,
  lightPlan,
  fittingOrientations,
  hasHorizontalOverlap,
  fanPreset,
  fanCeilingGapCm,
  setFanCeilingGapCm,
  heightCm,
  potMaxHeightCm,
}: LightsFormProps) {
  return (
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
  )
}
