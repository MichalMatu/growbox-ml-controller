import { useId, useState } from "react"

import { getConfigurationFeatureValue } from "@/domain/configuration"
import { formatUnit, getFeatureLabel } from "@/domain/labels"
import type { Configuration, FeatureDefinition, JsonValue } from "@/domain/types"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"

interface FeatureControlProps {
  feature: FeatureDefinition
  configuration: Configuration
  disabled?: boolean
  onValueChange: (path: string, value: JsonValue) => void
}

interface NumberControlProps {
  feature: FeatureDefinition
  value: number
  disabled: boolean
  onValueChange: (value: number) => void
}

function NumberControl({ feature, value, disabled, onValueChange }: NumberControlProps) {
  const id = useId()
  const [draft, setDraft] = useState(String(value))
  const [syncedValue, setSyncedValue] = useState(value)

  // Keep local draft in sync when the parent value changes (e.g. import / clamp).
  if (value !== syncedValue) {
    setSyncedValue(value)
    setDraft(String(value))
  }

  function commit(): void {
    const parsed = Number(draft)
    if (Number.isFinite(parsed)) {
      onValueChange(parsed)
      return
    }
    setDraft(String(value))
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{getFeatureLabel(feature)}</Label>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        min={feature.minimum}
        max={feature.maximum}
        step="any"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur()
        }}
      />
      <FieldMeta feature={feature} />
    </div>
  )
}

function FieldMeta({ feature }: { feature: FeatureDefinition }) {
  const range =
    feature.type === "number" ? `${feature.minimum}–${feature.maximum}` : formatUnit(feature)

  return (
    <p className="text-xs text-muted-foreground">
      {formatUnit(feature)} · {range} · <code>{feature.path}</code>
    </p>
  )
}

export function FeatureControl({
  feature,
  configuration,
  disabled = false,
  onValueChange,
}: FeatureControlProps) {
  const value = getConfigurationFeatureValue(configuration, feature)
  const controlId = useId()

  if (feature.type === "boolean") {
    return (
      <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-3">
        <div className="space-y-1">
          <Label htmlFor={controlId}>{getFeatureLabel(feature)}</Label>
          <FieldMeta feature={feature} />
        </div>
        <Switch
          id={controlId}
          checked={value === true}
          disabled={disabled}
          aria-label={getFeatureLabel(feature)}
          onCheckedChange={(checked) => onValueChange(feature.path, checked)}
        />
      </div>
    )
  }

  if (feature.type === "enum") {
    const enumValue = typeof value === "string" ? value : ""
    return (
      <div className="space-y-2 rounded-lg border border-border p-3">
        <Label htmlFor={controlId}>{getFeatureLabel(feature)}</Label>
        <Select
          value={enumValue}
          disabled={disabled}
          onValueChange={(nextValue) => onValueChange(feature.path, nextValue)}
        >
          <SelectTrigger id={controlId} className="w-full">
            <SelectValue placeholder="Wybierz rodzaj" />
          </SelectTrigger>
          <SelectContent>
            {Object.keys(feature.encoding ?? {}).map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FieldMeta feature={feature} />
      </div>
    )
  }

  const numberValue = typeof value === "number" ? value : feature.default
  return (
    <div className="rounded-lg border border-border p-3">
      <NumberControl
        feature={feature}
        value={numberValue}
        disabled={disabled}
        onValueChange={(nextValue) => onValueChange(feature.path, nextValue)}
      />
    </div>
  )
}
