import { useMemo, useState } from "react"

import { ChamberScene } from "@/chamber-3d/chamber-scene"
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

function clampCm(raw: string, fallback: number): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return fallback
  return Math.min(500, Math.max(10, value))
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
            Parametryczna namiotówka (W × D × H w cm). Ta strona nie zapisuje do JSON v4 —
            tylko eksperyment wizualny. Orbit: przeciągnij, zoom: scroll.
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
                UX-only (jak opcjonalny root <code>enclosure</code>). Tom = W·D·H /
                1e6 m³. PBR: FreePBR nylon + ambientCG Foil003, stelaż.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AppCardBody variant="form">
                <AppFormField label="Szerokość (cm)" htmlFor="width_cm">
                  <Input
                    id="width_cm"
                    type="number"
                    min={10}
                    max={500}
                    step={1}
                    value={widthCm}
                    onChange={(event) => setWidthCm(clampCm(event.target.value, widthCm))}
                  />
                </AppFormField>
                <AppFormField label="Głębokość (cm)" htmlFor="depth_cm">
                  <Input
                    id="depth_cm"
                    type="number"
                    min={10}
                    max={500}
                    step={1}
                    value={depthCm}
                    onChange={(event) => setDepthCm(clampCm(event.target.value, depthCm))}
                  />
                </AppFormField>
                <AppFormField label="Wysokość (cm)" htmlFor="height_cm">
                  <Input
                    id="height_cm"
                    type="number"
                    min={10}
                    max={500}
                    step={1}
                    value={heightCm}
                    onChange={(event) => setHeightCm(clampCm(event.target.value, heightCm))}
                  />
                </AppFormField>
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
