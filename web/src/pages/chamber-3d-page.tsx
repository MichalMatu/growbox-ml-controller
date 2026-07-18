import { useMemo, useState } from "react"

import { ChamberScene } from "@/chamber-3d/chamber-scene"
import {
  commitEnclosureCm,
  ENCLOSURE_CM_MAX,
  ENCLOSURE_CM_MIN,
  isLiveEnclosureCm,
  parseEnclosureCmDraft,
} from "@/chamber-3d/enclosure-cm"
import {
  AppActionRow,
  AppCanvasFrame,
  AppCardBody,
  AppFormField,
  AppMutedText,
  AppPage,
  AppPageFooter,
  AppPageHeader,
  AppPreviewSplit,
} from "@/components/app-chrome"
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
import { navigate, ROUTES } from "@/lib/routing"

const DEFAULT_WIDTH_CM = 80
const DEFAULT_DEPTH_CM = 80
const DEFAULT_HEIGHT_CM = 160

type CmFieldProps = {
  id: string
  label: string
  valueCm: number
  onValueCmChange: (nextCm: number) => void
}

/**
 * Draft string while typing; clamp only on blur / Enter.
 * Live 3D updates only when the draft is already within min–max.
 */
function CmDimensionField({ id, label, valueCm, onValueCmChange }: CmFieldProps) {
  const [draft, setDraft] = useState(String(valueCm))
  const [syncedCm, setSyncedCm] = useState(valueCm)

  if (valueCm !== syncedCm) {
    setSyncedCm(valueCm)
    setDraft(String(valueCm))
  }

  function commit(): void {
    const next = commitEnclosureCm(draft, valueCm)
    onValueCmChange(next)
    setDraft(String(next))
  }

  return (
    <AppFormField label={label} htmlFor={id}>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={ENCLOSURE_CM_MIN}
        max={ENCLOSURE_CM_MAX}
        step={1}
        value={draft}
        onChange={(event) => {
          const raw = event.target.value
          setDraft(raw)
          const parsed = parseEnclosureCmDraft(raw)
          if (parsed !== null && isLiveEnclosureCm(parsed)) {
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

/**
 * Isolated R3F playground. DOM chrome only via app-chrome + shadcn.
 * No freehand Tailwind in this file (enforced by lint/tests).
 */
export function Chamber3dPage() {
  const [widthCm, setWidthCm] = useState(DEFAULT_WIDTH_CM)
  const [depthCm, setDepthCm] = useState(DEFAULT_DEPTH_CM)
  const [heightCm, setHeightCm] = useState(DEFAULT_HEIGHT_CM)

  const volumeM3 = useMemo(
    () => (widthCm * depthCm * heightCm) / 1_000_000,
    [widthCm, depthCm, heightCm],
  )

  return (
    <AppPage width="wide">
      <AppPageHeader
        title="Podgląd komory 3D"
        badges={
          <>
            <Badge variant="secondary">R3F playground</Badge>
            <Badge variant="outline">oddzielone od konfiguratora</Badge>
          </>
        }
        description={
          <>
            Parametryczna namiotówka (W × D × H w cm, min {ENCLOSURE_CM_MIN}). Ta strona nie
            zapisuje do JSON v4 — tylko eksperyment wizualny. Orbit: przeciągnij, zoom:
            scroll.
          </>
        }
        actions={
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(ROUTES.configurator)}
          >
            Wróć do konfiguratora
          </Button>
        }
      />

      <AppPreviewSplit
        sidebar={
          <Card>
            <CardHeader>
              <CardTitle>Wymiary komory</CardTitle>
              <CardDescription>
                UX-only (jak opcjonalny root <code>enclosure</code>). Zakres{" "}
                {ENCLOSURE_CM_MIN}–{ENCLOSURE_CM_MAX} cm. Tom = W·D·H / 1e6 m³.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AppCardBody variant="form">
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
                />
                <AppMutedText>Objętość: {volumeM3.toFixed(4)} m³</AppMutedText>
                <AppActionRow>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setWidthCm(DEFAULT_WIDTH_CM)
                      setDepthCm(DEFAULT_DEPTH_CM)
                      setHeightCm(DEFAULT_HEIGHT_CM)
                    }}
                  >
                    Reset
                  </Button>
                </AppActionRow>
              </AppCardBody>
            </CardContent>
          </Card>
        }
        main={
          <AppCanvasFrame>
            <ChamberScene
              widthCm={widthCm}
              depthCm={depthCm}
              heightCm={heightCm}
            />
          </AppCanvasFrame>
        }
      />

      <AppPageFooter>
        Podgląd 3D · bez zapisu do JSON · shell: <code>AppPage</code>
      </AppPageFooter>
    </AppPage>
  )
}
