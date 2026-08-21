import {
  AppControlSurface,
  AppFormField,
  AppFormGrid,
} from "@/components/app-chrome"
import { Input } from "@/components/ui/input"
import { CmDimensionField } from "./cm-dimension-field"

type EnclosureFormProps = {
  widthCm: number
  setWidthCm: (cm: number) => void
  depthCm: number
  setDepthCm: (cm: number) => void
  heightCm: number
  setHeightCm: (cm: number) => void
  volumeM3: number
}

export function EnclosureForm({
  widthCm,
  setWidthCm,
  depthCm,
  setDepthCm,
  heightCm,
  setHeightCm,
  volumeM3,
}: EnclosureFormProps) {
  return (
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
  )
}
