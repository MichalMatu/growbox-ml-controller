import { useState } from "react"
import { useChamberPhysics, type PotKey } from "@/chamber-3d/hooks/use-chamber-physics"

import { ChamberCanvas } from "@/chamber-3d/core/chamber-scene"
import { ChamberPerformanceProvider } from "@/chamber-3d/performance/performance-context"
import { PerformanceOverlay } from "@/chamber-3d/performance/performance-overlay"
import { type FeltPotCount } from "@/chamber-3d/components/pots/felt-pot-geometry"
import { type RoomLayout } from "@/chamber-3d/environment/room"
import {
  DEFAULT_LIGHT_CEILING_GAP_CM,
  DEFAULT_LIGHT_ORIENTATION_DEG,
  DEFAULT_LIGHT_PRESET_ID,
  type LightOrientationDeg,
  type LightPresetId,
} from "@/chamber-3d/components/lights/light-geometry"
import {
  DEFAULT_FAN_CEILING_GAP_CM,
  DEFAULT_FAN_ORIENTATION_DEG,
  DEFAULT_FAN_POSITION,
  DEFAULT_FAN_PRESET_ID,
  type FanOrientationDeg,
  type FanPosition,
  type FanPresetId,
} from "@/chamber-3d/components/fans/fan-geometry"
import { EnclosureForm } from "@/chamber-3d/components/forms/enclosure-form"
import { PotsForm } from "@/chamber-3d/components/forms/pots-form"
import { LightsForm } from "@/chamber-3d/components/forms/lights-form"
import { FansForm } from "@/chamber-3d/components/forms/fans-form"
import { CmDimensionField } from "@/chamber-3d/components/forms/cm-dimension-field"

import {
  AppActionRow,
  AppCanvasFrame,
  AppCardBody,
  AppControlSurface,
  AppFormField,
  AppFormGrid,
  AppPage,
  AppPreviewSplit,
  AppSelectTrigger,
} from "@/components/app-chrome"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select"
import { navigate, ROUTES } from "@/lib/routing"

const DEFAULT_WIDTH_CM = 80
const DEFAULT_DEPTH_CM = 80
const DEFAULT_HEIGHT_CM = 160
const DEFAULT_WALL_HEIGHT_CM = 260
const DEFAULT_POT_COUNT: FeltPotCount = 1

const DEFAULT_POT_KEY: PotKey = "felt/12l"



export function Chamber3dPage() {
  const [widthCm, setWidthCm] = useState(DEFAULT_WIDTH_CM)
  const [depthCm, setDepthCm] = useState(DEFAULT_DEPTH_CM)
  const [heightCm, setHeightCm] = useState(DEFAULT_HEIGHT_CM)
  const [potKey, setPotKey] = useState<PotKey>(DEFAULT_POT_KEY)
  const [potCount, setPotCount] = useState<FeltPotCount>(DEFAULT_POT_COUNT)
  const [lightPresetId, setLightPresetId] = useState<LightPresetId>(DEFAULT_LIGHT_PRESET_ID)
  const [lightOrientationDeg, setLightOrientationDeg] =
    useState<LightOrientationDeg>(DEFAULT_LIGHT_ORIENTATION_DEG)
  const [lightCeilingGapCm, setLightCeilingGapCm] = useState(DEFAULT_LIGHT_CEILING_GAP_CM)
  const [lightOn, setLightOn] = useState(true)
  const [fanPresetId, setFanPresetId] = useState<FanPresetId>(DEFAULT_FAN_PRESET_ID)
  const [fanOrientationDeg, setFanOrientationDeg] =
    useState<FanOrientationDeg>(DEFAULT_FAN_ORIENTATION_DEG)
  const [fanCeilingGapCm, setFanCeilingGapCm] = useState(DEFAULT_FAN_CEILING_GAP_CM)
  const [fanPosition, setFanPosition] = useState<FanPosition>(DEFAULT_FAN_POSITION)
  const [roomLayout, setRoomLayout] = useState<RoomLayout>("flat")
  const [wallHeightCm, setWallHeightCm] = useState(DEFAULT_WALL_HEIGHT_CM)

  const {
    volumeM3,
    potType,
    maxFit,
    visiblePotCount,
    potMaxHeightCm,
    lightPreset,
    fanPreset,
    fittingOrientations,
    effectiveLightOrientationDeg,
    fanFittingOrientations,
    effectiveFanOrientationDeg,
    lightPlan,
    fanPlan,
    effectiveLightCeilingGapCm,
    effectiveFanCeilingGapCm,
    baseLightPlan,
    hasHorizontalOverlap,
    potPresetId,
  } = useChamberPhysics({
    widthCm,
    depthCm,
    heightCm,
    potKey,
    defaultPotKey: DEFAULT_POT_KEY,
    potCount,
    lightPresetId,
    lightOrientationDeg,
    lightCeilingGapCm,
    fanPresetId,
    fanOrientationDeg,
    fanCeilingGapCm,
    fanPosition,
  })



  return (
    <AppPage width="wide">
      <AppPreviewSplit
        sidebar={
          <Card>
            <CardHeader>
              <CardTitle>Ustawienia</CardTitle>
              <CardAction>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate(ROUTES.configurator)}
                >
                  Wróć
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent>
              <AppCardBody variant="form">
                <EnclosureForm
                  widthCm={widthCm}
                  setWidthCm={setWidthCm}
                  depthCm={depthCm}
                  setDepthCm={setDepthCm}
                  heightCm={heightCm}
                  setHeightCm={setHeightCm}
                  volumeM3={volumeM3}
                />

                <PotsForm
                  potKey={potKey}
                  setPotKey={setPotKey}
                  potCount={potCount}
                  setPotCount={setPotCount}
                  maxFit={maxFit}
                  visiblePotCount={visiblePotCount}
                />

                <LightsForm
                  lightPresetId={lightPresetId}
                  setLightPresetId={setLightPresetId}
                  setLightOrientationDeg={setLightOrientationDeg}
                  setLightCeilingGapCm={setLightCeilingGapCm}
                  lightOn={lightOn}
                  setLightOn={setLightOn}
                  effectiveLightOrientationDeg={effectiveLightOrientationDeg}
                  effectiveLightCeilingGapCm={effectiveLightCeilingGapCm}
                  lightPreset={lightPreset}
                  lightPlan={lightPlan}
                  fittingOrientations={fittingOrientations}
                  hasHorizontalOverlap={hasHorizontalOverlap}
                  fanPreset={fanPreset}
                  fanCeilingGapCm={fanCeilingGapCm}
                  setFanCeilingGapCm={setFanCeilingGapCm}
                  heightCm={heightCm}
                  potMaxHeightCm={potMaxHeightCm}
                />

                <FansForm
                  fanPresetId={fanPresetId}
                  setFanPresetId={setFanPresetId}
                  setFanOrientationDeg={setFanOrientationDeg}
                  setFanCeilingGapCm={setFanCeilingGapCm}
                  fanPosition={fanPosition}
                  setFanPosition={setFanPosition}
                  effectiveFanOrientationDeg={effectiveFanOrientationDeg}
                  effectiveFanCeilingGapCm={effectiveFanCeilingGapCm}
                  fanPreset={fanPreset}
                  fanPlan={fanPlan}
                  fanFittingOrientations={fanFittingOrientations}
                  hasHorizontalOverlap={hasHorizontalOverlap}
                  lightPreset={lightPreset}
                  lightCeilingGapCm={lightCeilingGapCm}
                  setLightCeilingGapCm={setLightCeilingGapCm}
                  baseLightPlan={baseLightPlan}
                  heightCm={heightCm}
                  potMaxHeightCm={potMaxHeightCm}
                />

                <AppControlSurface>
                  <AppFormGrid>
                    <AppFormField label="Tło sceny" htmlFor="room_layout">
                      <Select
                        value={roomLayout}
                        onValueChange={(value) => setRoomLayout(value as RoomLayout)}
                      >
                        <AppSelectTrigger id="room_layout">
                          <SelectValue placeholder="Tło" />
                        </AppSelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Studio (bez ścian)</SelectItem>
                          <SelectItem value="flat">Przy ścianie</SelectItem>
                          <SelectItem value="corner">W rogu</SelectItem>
                        </SelectContent>
                      </Select>
                    </AppFormField>

                    <CmDimensionField
                      id="wall_height_cm"
                      label="Wys. ściany (cm)"
                      valueCm={wallHeightCm}
                      onValueCmChange={setWallHeightCm}
                      maxCm={260}
                    />
                  </AppFormGrid>
                </AppControlSurface>

                <AppActionRow align="end">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setWidthCm(DEFAULT_WIDTH_CM)
                      setDepthCm(DEFAULT_DEPTH_CM)
                      setHeightCm(DEFAULT_HEIGHT_CM)
                      setPotKey(DEFAULT_POT_KEY)
                      setPotCount(DEFAULT_POT_COUNT)
                      setLightPresetId(DEFAULT_LIGHT_PRESET_ID)
                      setLightOrientationDeg(DEFAULT_LIGHT_ORIENTATION_DEG)
                      setLightCeilingGapCm(DEFAULT_LIGHT_CEILING_GAP_CM)
                      setLightOn(true)
                      setFanPresetId(DEFAULT_FAN_PRESET_ID)
                      setFanOrientationDeg(DEFAULT_FAN_ORIENTATION_DEG)
                      setFanCeilingGapCm(DEFAULT_FAN_CEILING_GAP_CM)
                      setFanPosition(DEFAULT_FAN_POSITION)
                      setWallHeightCm(DEFAULT_WALL_HEIGHT_CM)
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
            <ChamberPerformanceProvider>
              <PerformanceOverlay />
              <ChamberCanvas
                widthCm={widthCm}
                depthCm={depthCm}
                heightCm={heightCm}
                potType={potType}
                potPresetId={potPresetId}
                potCount={visiblePotCount}
                lightPresetId={lightPresetId}
                lightOrientationDeg={effectiveLightOrientationDeg}
                lightCeilingGapCm={effectiveLightCeilingGapCm}
                lightOn={lightOn && lightPlan.fits}
                fanPresetId={fanPresetId}
                fanOrientationDeg={effectiveFanOrientationDeg}
                fanCeilingGapCm={effectiveFanCeilingGapCm}
                fanPosition={fanPosition}
                roomLayout={roomLayout}
                wallHeightCm={wallHeightCm}
              />
            </ChamberPerformanceProvider>
          </AppCanvasFrame>
        }
      />
    </AppPage>
  )
}
