import {
  AppControlSurface,
  AppFormField,
  AppFormGrid,
  AppSelectTrigger,
} from "@/components/app-chrome"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectValue,
} from "@/components/ui/select"
import {
  FELT_POT_COUNT_MAX,
  FELT_POT_PRESETS,
  clampFeltPotCount,
  type FeltPotCount,
} from "@/chamber-3d/components/pots/felt-pot-geometry"
import { SQUARE_POT_PRESETS } from "@/chamber-3d/components/pots/square-pot-geometry"
import type { PotKey } from "@/chamber-3d/hooks/use-chamber-physics"

type PotsFormProps = {
  potKey: PotKey
  setPotKey: (key: PotKey) => void
  potCount: FeltPotCount
  setPotCount: (count: FeltPotCount) => void
  maxFit: number
  visiblePotCount: number
}

export function PotsForm({
  potKey,
  setPotKey,
  potCount,
  setPotCount,
  maxFit,
  visiblePotCount,
}: PotsFormProps) {
  return (
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
  )
}
