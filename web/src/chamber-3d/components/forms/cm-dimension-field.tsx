import { useState } from "react"
import { ENCLOSURE_CM_MAX, ENCLOSURE_CM_MIN, parseEnclosureCmDraft } from "@/chamber-3d/components/enclosure/enclosure-cm"
import { AppFormField } from "@/components/app-chrome"
import { Input } from "@/components/ui/input"

export type CmFieldProps = {
  id: string
  label: string
  valueCm: number
  onValueCmChange: (nextCm: number) => void
  minCm?: number
  maxCm?: number
  end?: React.ReactNode
}

export function CmDimensionField({
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
