import { useMemo, useRef, useState } from "react"

import {
  AppActionRow,
  AppCardBody,
  AppErrorList,
  AppFormField,
  AppHiddenFileInput,
  AppMutedText,
  AppPage,
  AppPageFooter,
  AppPageHeader,
  AppSection,
  AppSectionIntro,
  AppStack,
  AppSubsectionTitle,
} from "@/components/app-chrome"
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
import { Separator } from "@/components/ui/separator"
import {
  buildExportConfiguration,
  createDefaultConfiguration,
  parseConfigurationJson,
  updateFeatureValue,
  updateMetadata,
} from "@/domain/configuration"
import { schema } from "@/domain/schema"
import type { Configuration, JsonValue } from "@/domain/types"
import { navigate, ROUTES } from "@/lib/routing"
import { actuatorTitle, featuresForGroup, potTitle, UI_GROUPS } from "@/app/ui-groups"

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
    <AppPage width="standard">
      <AppPageHeader
        title="Konfigurator sprzętu growbox"
        badges={
          <>
            <Badge variant="secondary">schema v{schema.schema_version}</Badge>
            <Badge variant="outline">{featureCount} features</Badge>
          </>
        }
        description={
          <>
            Opisz zainstalowany sprzęt w kontrakcie v4 i pobierz jeden plik JSON.
            Brak modułu = <code>available/validity = false</code> i zerowe pola
            capability — sloty doniczek zawsze zostają (4).
          </>
        }
        actions={
          <Button type="button" variant="outline" onClick={() => navigate(ROUTES.chamber3d)}>
            Podgląd 3D (osobna strona)
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Metadane eksportu</CardTitle>
          <CardDescription>
            Opcjonalne klucze root spoza ML features (title, profile_id, seed).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AppCardBody variant="form">
            <AppFormField label="Tytuł" htmlFor="title">
              <Input
                id="title"
                value={typeof configuration.title === "string" ? configuration.title : ""}
                onChange={(event) => handleMetadata("title", event.target.value)}
              />
            </AppFormField>
            <AppFormField label="Profile ID" htmlFor="profile_id">
              <Input
                id="profile_id"
                value={
                  typeof configuration.profile_id === "string" ? configuration.profile_id : ""
                }
                onChange={(event) => handleMetadata("profile_id", event.target.value)}
              />
            </AppFormField>
            <AppFormField label="Seed" htmlFor="seed">
              <Input
                id="seed"
                type="number"
                step={1}
                value={typeof configuration.seed === "number" ? configuration.seed : 0}
                onChange={(event) => handleMetadata("seed", event.target.value)}
              />
            </AppFormField>
          </AppCardBody>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import / eksport</CardTitle>
          <CardDescription>
            Import przyjmuje wyłącznie dokument przechodzący te same reguły co eksport v4.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AppCardBody variant="stack">
            <AppActionRow>
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
              <AppHiddenFileInput
                ref={fileInputRef}
                accept="application/json,.json"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  event.target.value = ""
                  if (file) void handleImportFile(file)
                }}
              />
            </AppActionRow>
            {statusMessage ? <AppMutedText>{statusMessage}</AppMutedText> : null}
            <AppErrorList errors={importErrors} />
          </AppCardBody>
        </CardContent>
      </Card>

      {grouped.map((group) => (
        <AppSection key={group.id}>
          <AppSectionIntro title={group.title} description={group.description} />
          <AppStack gap="md">
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
                <AppStack key={feature.path} gap="sm">
                  {showPotDivider ? (
                    <>
                      {index > 0 ? <Separator /> : null}
                      <AppSubsectionTitle>{pot}</AppSubsectionTitle>
                    </>
                  ) : null}
                  {showActuatorDivider ? (
                    <>
                      {index > 0 && !showPotDivider ? <Separator /> : null}
                      <AppSubsectionTitle>{actuator}</AppSubsectionTitle>
                    </>
                  ) : null}
                  <FeatureControl
                    feature={feature}
                    configuration={configuration}
                    disabled={previousFeature}
                    onValueChange={handleFeatureChange}
                  />
                </AppStack>
              )
            })}
          </AppStack>
        </AppSection>
      ))}

      <AppPageFooter>
        SSOT: <code>schemas/environment-controller.json</code> · gate:{" "}
        <code>pnpm gate</code>
      </AppPageFooter>
    </AppPage>
  )
}

export default App
