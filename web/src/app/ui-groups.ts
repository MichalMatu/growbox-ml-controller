import { getActuatorLabel } from "@/domain/labels"
import { schema } from "@/domain/schema"
import type { FeatureDefinition } from "@/domain/types"

export const UI_GROUPS: Array<{
  id: string
  title: string
  description: string
  match: (path: string) => boolean
}> = [
  {
    id: "chamber",
    title: "Komora",
    description: "environment.* — geometria i właściwości cieplne namiotu.",
    match: (path) => path.startsWith("environment."),
  },
  {
    id: "sensors",
    title: "Czujniki i validity",
    description: "sensors.* oraz validity.* dla pomiarów globalnych.",
    match: (path) => path.startsWith("sensors.") || path.startsWith("validity."),
  },
  {
    id: "pseudo",
    title: "Pseudo",
    description:
      "Harmonogram światła jako pseudo.lights_active (bez actuators.lights).",
    match: (path) => path.startsWith("pseudo."),
  },
  {
    id: "pots",
    title: "Doniczki 1–4",
    description:
      "Zawsze 4 sloty; brak sprzętu = available/validity false + zerowe capability.",
    match: (path) => path.startsWith("pots."),
  },
  {
    id: "actuators",
    title: "Wyjścia globalne",
    description: "actuators.* bez control_type i bez lights.",
    match: (path) => path.startsWith("actuators."),
  },
  {
    id: "targets",
    title: "Cele",
    description: "targets.* — domyślne cele środowiskowe.",
    match: (path) => path.startsWith("targets."),
  },
  {
    id: "previous",
    title: "Previous (szablon)",
    description:
      "W eksporcie sprzętowym wszystkie previous.* = 0 (tylko podgląd).",
    match: (path) =>
      path.startsWith("previous.") || /^pots\.\d+\.previous\./.test(path),
  },
]

export function featuresForGroup(groupId: string): FeatureDefinition[] {
  const group = UI_GROUPS.find((item) => item.id === groupId)
  if (!group) return []
  return schema.model.features.filter((feature) => group.match(feature.path))
}

export function potTitle(path: string): string | null {
  const match = /^pots\.(\d+)\./.exec(path)
  if (!match) return null
  return `Doniczka ${Number(match[1]) + 1}`
}

export function actuatorTitle(path: string): string | null {
  const match = /^actuators\.([^.]+)\./.exec(path)
  if (!match?.[1]) return null
  return getActuatorLabel(match[1])
}
