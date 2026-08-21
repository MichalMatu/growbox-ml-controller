import { useId, useState } from "react"

import {
  AppControlLabelBlock,
  AppControlSurface,
  AppFieldMetaText,
  AppFieldStack,
  AppSelectTrigger,
} from "@/components/app-chrome"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { getConfigurationFeatureValue } from "@/domain/configuration"
import { formatUnit, getFeatureLabel } from "@/domain/labels"
import type { Configuration, FeatureDefinition, JsonValue } from "@/domain/types"

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
    <AppFieldStack>
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
    </AppFieldStack>
  )
}

function FieldMeta({ feature }: { feature: FeatureDefinition }) {
  const range =
    feature.type === "number" ? `${feature.minimum}–${feature.maximum}` : formatUnit(feature)

  return (
    <AppFieldMetaText>
      {formatUnit(feature)} · {range} · <code>{feature.path}</code>
    </AppFieldMetaText>
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
      <AppControlSurface variant="row">
        <AppControlLabelBlock>
          <Label htmlFor={controlId}>{getFeatureLabel(feature)}</Label>
          <FieldMeta feature={feature} />
        </AppControlLabelBlock>
        <Switch
          id={controlId}
          checked={value === true}
          disabled={disabled}
          aria-label={getFeatureLabel(feature)}
          onCheckedChange={(checked) => onValueChange(feature.path, checked)}
        />
      </AppControlSurface>
    )
  }

  if (feature.type === "enum") {
    const enumValue = typeof value === "string" ? value : ""
    return (
      <AppControlSurface variant="stack">
        <Label htmlFor={controlId}>{getFeatureLabel(feature)}</Label>
        <Select
          value={enumValue}
          disabled={disabled}
          onValueChange={(nextValue) => onValueChange(feature.path, nextValue)}
        >
          <AppSelectTrigger id={controlId}>
            <SelectValue placeholder="Wybierz rodzaj" />
          </AppSelectTrigger>
          <SelectContent>
            {Object.keys(feature.encoding ?? {}).map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FieldMeta feature={feature} />
      </AppControlSurface>
    )
  }

  const numberValue = typeof value === "number" ? value : feature.default
  return (
    <AppControlSurface variant="stack">
      <NumberControl
        feature={feature}
        value={numberValue}
        disabled={disabled}
        onValueChange={(nextValue) => onValueChange(feature.path, nextValue)}
      />
    </AppControlSurface>
  )
}
