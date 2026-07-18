import { useMemo, useState } from "react"

import { ChamberScene } from "@/chamber-3d/chamber-scene"
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
 * Isolated R3F playground. Does not import or mutate configurator domain state.
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
    <div className="mx-auto flex min-h-svh w-full max-w-5xl flex-col gap-6 p-6">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">Podgląd komory 3D</h1>
          <Badge variant="secondary">R3F playground</Badge>
          <Badge variant="outline">oddzielone od konfiguratora</Badge>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Parametryczna namiotówka (W × D × H w cm). Ta strona nie zapisuje do JSON v4 —
          tylko eksperyment wizualny. Orbit: przeciągnij, zoom: scroll.
        </p>
        <div>
          <Button type="button" variant="outline" onClick={() => navigate(ROUTES.configurator)}>
            ← Wróć do konfiguratora
          </Button>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Wymiary enclosure</CardTitle>
            <CardDescription>
              UX-only (jak opcjonalny root <code>enclosure</code>). Tom = W·D·H / 1e6 m³.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="width_cm">Szerokość (cm)</Label>
              <Input
                id="width_cm"
                type="number"
                min={10}
                max={500}
                step={1}
                value={widthCm}
                onChange={(event) =>
                  setWidthCm(clampCm(event.target.value, widthCm))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="depth_cm">Głębokość (cm)</Label>
              <Input
                id="depth_cm"
                type="number"
                min={10}
                max={500}
                step={1}
                value={depthCm}
                onChange={(event) =>
                  setDepthCm(clampCm(event.target.value, depthCm))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="height_cm">Wysokość (cm)</Label>
              <Input
                id="height_cm"
                type="number"
                min={10}
                max={500}
                step={1}
                value={heightCm}
                onChange={(event) =>
                  setHeightCm(clampCm(event.target.value, heightCm))
                }
              />
            </div>
            <p className="text-sm text-muted-foreground">
              Objętość:{" "}
              <span className="font-medium text-foreground">
                {volumeM3.toFixed(4)} m³
              </span>
            </p>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setWidthCm(DEFAULT_WIDTH_CM)
                setDepthCm(DEFAULT_DEPTH_CM)
                setHeightCm(DEFAULT_HEIGHT_CM)
              }}
            >
              Reset 80×80×160
            </Button>
          </CardContent>
        </Card>

        <Card className="overflow-hidden p-0">
          <CardContent className="h-[min(70vh,36rem)] p-0">
            <ChamberScene
              widthCm={widthCm}
              depthCm={depthCm}
              heightCm={heightCm}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
