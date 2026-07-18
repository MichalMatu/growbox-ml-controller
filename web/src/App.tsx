import { useMemo, useRef, useState } from "react"

import { FeatureControl } from "@/components/feature-control"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  buildExportConfiguration,
  createDefaultConfiguration,
  parseConfigurationJson,
  updateFeatureValue,
  updateMetadata,
} from "@/domain/configuration"
import { getActuatorLabel } from "@/domain/labels"
import { schema } from "@/domain/schema"
import type { Configuration, FeatureDefinition, JsonValue } from "@/domain/types"

const UI_GROUPS: Array<{ id: string; title: string; description: string; match: (path: string) => boolean }> =
  [
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
      description: "Harmonogram światła jako pseudo.lights_active (bez actuators.lights).",
      match: (path) => path.startsWith("pseudo."),
    },
    {
      id: "pots",
      title: "Doniczki 1–4",
      description: "Zawsze 4 sloty; brak sprzętu = available/validity false + zerowe capability.",
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
      description: "W eksporcie sprzętowym wszystkie previous.* = 0 (tylko podgląd).",
      match: (path) => path.startsWith("previous.") || /^pots\.\d+\.previous\./.test(path),
    },
  ]

function featuresForGroup(groupId: string): FeatureDefinition[] {
  const group = UI_GROUPS.find((item) => item.id === groupId)
  if (!group) return []
  return schema.model.features.filter((feature) => group.match(feature.path))
}

function potTitle(path: string): string | null {
  const match = /^pots\.(\d+)\./.exec(path)
  if (!match) return null
  return `Doniczka ${Number(match[1]) + 1}`
}

function actuatorTitle(path: string): string | null {
  const match = /^actuators\.([^.]+)\./.exec(path)
  if (!match?.[1]) return null
  return getActuatorLabel(match[1])
}

function downloadConfiguration(configuration: Configuration): void {
  const exported = buildExportConfiguration(configuration)
  const blob = new Blob([`${JSON.stringify(exported, null, 2)}\n`], {
    type: "application/json",
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  const stamp = new Date().toISOString().slice(0, 10)
  const profile =
    typeof exported.profile_id === "string" && exported.profile_id.length > 0
      ? exported.profile_id
      : "growbox-v4"
  anchor.href = url
  anchor.download = `${profile}-${stamp}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

export function App() {
  const [configuration, setConfiguration] = useState<Configuration>(() =>
    createDefaultConfiguration(),
  )
  const [importErrors, setImportErrors] = useState<string[]>([])
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const featureCount = schema.model.features.length

  const grouped = useMemo(() => {
    return UI_GROUPS.map((group) => ({
      ...group,
      features: featuresForGroup(group.id).filter((feature) => {
        // previous.* pot paths are already under pots group match; keep them only in previous.
        if (group.id === "pots" && /^pots\.\d+\.previous\./.test(feature.path)) return false
        return true
      }),
    }))
  }, [])

  function handleFeatureChange(path: string, value: JsonValue): void {
    setConfiguration((current) => updateFeatureValue(current, path, value))
    setStatusMessage(null)
  }

  function handleMetadata(
    key: "title" | "profile_id" | "seed",
    raw: string,
  ): void {
    if (key === "seed") {
      const parsed = Number(raw)
      setConfiguration((current) =>
        updateMetadata(current, "seed", Number.isInteger(parsed) ? parsed : 0),
      )
      return
    }
    setConfiguration((current) => updateMetadata(current, key, raw))
  }

  async function handleImportFile(file: File): Promise<void> {
    const text = await file.text()
    const result = parseConfigurationJson(text)
    if (!result.success) {
      setImportErrors(result.errors)
      setStatusMessage("Import odrzucony — popraw błędy w pliku JSON.")
      return
    }
    setConfiguration(result.configuration)
    setImportErrors([])
    setStatusMessage(`Zaimportowano: ${file.name}`)
  }

  return (
    <div className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-6 p-6">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">
            Konfigurator sprzętu growbox
          </h1>
          <Badge variant="secondary">schema v{schema.schema_version}</Badge>
          <Badge variant="outline">{featureCount} features</Badge>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Opisz zainstalowany sprzęt w kontrakcie v4 i pobierz jeden plik JSON.
          Brak modułu = <code>available/validity = false</code> i zerowe pola
          capability — sloty doniczek zawsze zostają (4).
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Metadane eksportu</CardTitle>
          <CardDescription>
            Opcjonalne klucze root spoza ML features (title, profile_id, seed).
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="title">Tytuł</Label>
            <Input
              id="title"
              value={typeof configuration.title === "string" ? configuration.title : ""}
              onChange={(event) => handleMetadata("title", event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="profile_id">Profile ID</Label>
            <Input
              id="profile_id"
              value={
                typeof configuration.profile_id === "string" ? configuration.profile_id : ""
              }
              onChange={(event) => handleMetadata("profile_id", event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="seed">Seed</Label>
            <Input
              id="seed"
              type="number"
              step={1}
              value={typeof configuration.seed === "number" ? configuration.seed : 0}
              onChange={(event) => handleMetadata("seed", event.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import / eksport</CardTitle>
          <CardDescription>
            Import przyjmuje wyłącznie dokument przechodzący te same reguły co eksport v4.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => downloadConfiguration(configuration)}>
              Pobierz JSON
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
            >
              Importuj JSON
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setConfiguration(createDefaultConfiguration())
                setImportErrors([])
                setStatusMessage("Przywrócono domyślną konfigurację.")
              }}
            >
              Reset
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ""
                if (file) void handleImportFile(file)
              }}
            />
          </div>
          {statusMessage ? (
            <p className="text-sm text-muted-foreground">{statusMessage}</p>
          ) : null}
          {importErrors.length > 0 ? (
            <ul className="list-disc space-y-1 rounded-lg border border-destructive/40 bg-destructive/5 p-3 pl-6 text-sm text-destructive">
              {importErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      {grouped.map((group) => (
        <section key={group.id} className="flex flex-col gap-3">
          <div>
            <h2 className="text-lg font-medium">{group.title}</h2>
            <p className="text-sm text-muted-foreground">{group.description}</p>
          </div>
          <div className="flex flex-col gap-3">
            {group.features.map((feature, index) => {
              const pot = potTitle(feature.path)
              const actuator = actuatorTitle(feature.path)
              const previousFeature =
                feature.path.startsWith("previous.") ||
                /^pots\.\d+\.previous\./.test(feature.path)
              const showPotDivider =
                pot !== null &&
                (index === 0 || potTitle(group.features[index - 1]?.path ?? "") !== pot)
              const showActuatorDivider =
                actuator !== null &&
                (index === 0 ||
                  actuatorTitle(group.features[index - 1]?.path ?? "") !== actuator)

              return (
                <div key={feature.path} className="flex flex-col gap-2">
                  {showPotDivider ? (
                    <>
                      {index > 0 ? <Separator /> : null}
                      <h3 className="text-sm font-medium text-foreground">{pot}</h3>
                    </>
                  ) : null}
                  {showActuatorDivider ? (
                    <>
                      {index > 0 && !showPotDivider ? <Separator /> : null}
                      <h3 className="text-sm font-medium text-foreground">{actuator}</h3>
                    </>
                  ) : null}
                  <FeatureControl
                    feature={feature}
                    configuration={configuration}
                    disabled={previousFeature}
                    onValueChange={handleFeatureChange}
                  />
                </div>
              )
            })}
          </div>
        </section>
      ))}

      <footer className="pb-8 text-xs text-muted-foreground">
        SSOT: <code>schemas/environment-controller.json</code> · gate:{" "}
        <code>pnpm gate</code>
      </footer>
    </div>
  )
}

export default App
