import { useMemo } from "react"
import { Text } from "@react-three/drei"

import type { ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"

/**
 * Ruler inside the tent's back panel (Studio / no room walls).
 * Positioned at the right edge of the interior back wall, 15 cm from tent edge.
 */
export function TentRuler({
  widthM,
  depthM,
  heightM,
  thicknessM,
  colors,
}: {
  widthM: number
  depthM: number
  heightM: number
  thicknessM: number
  colors: ChamberSceneColors
}) {
  const ticks = useMemo(() => {
    const items: Array<{ y: number; isMajor: boolean; label?: string }> = []
    const stepCm = 5
    const maxCm = Math.floor(heightM * 100)

    for (let cm = 0; cm <= maxCm; cm += stepCm) {
      const y = cm / 100
      const isMajor = cm % 10 === 0
      items.push({ y, isMajor, label: isMajor ? `${cm}` : undefined })
    }
    return items
  }, [heightM])

  const interiorZ = -depthM / 2 + thicknessM
  const rulerZ = interiorZ + 0.002
  // 15 cm to the right of the tent's right edge (visible on the foil, not behind tent).
  const rulerX = widthM / 2 + 0.15

  return <RulerMarks ticks={ticks} rulerX={rulerX} rulerZ={rulerZ} tickDepth={0.003} colors={colors} />
}

/**
 * Vertical ruler on the room's back wall inner face.
 * Positioned 15 cm from the tent's right edge (not the wall edge).
 */
export function RoomWallRuler({
  wallHeightM,
  wallInnerZ,
  tentRightX,
  colors,
}: {
  wallHeightM: number
  wallInnerZ: number
  /** World X of the tent's right edge (half-width in meters). */
  tentRightX: number
  colors: ChamberSceneColors
}) {
  const ticks = useMemo(() => {
    const items: Array<{ y: number; isMajor: boolean; label?: string }> = []
    const stepCm = 5
    const maxCm = Math.floor(wallHeightM * 100)

    for (let cm = 0; cm <= maxCm; cm += stepCm) {
      const y = cm / 100
      const isMajor = cm % 10 === 0
      items.push({ y, isMajor, label: isMajor ? `${cm}` : undefined })
    }
    return items
  }, [wallHeightM])

  const rulerZ = wallInnerZ + 0.004
  // 15 cm to the right of the tent's right edge (visible on the wall, not behind tent).
  const rulerX = tentRightX + 0.15

  return <RulerMarks ticks={ticks} rulerX={rulerX} rulerZ={rulerZ} tickDepth={0.004} colors={colors} />
}

/** Shared dash marks + labels. */
function RulerMarks({
  ticks,
  rulerX,
  rulerZ,
  tickDepth,
  colors,
}: {
  ticks: Array<{ y: number; isMajor: boolean; label?: string }>
  rulerX: number
  rulerZ: number
  tickDepth: number
  colors: ChamberSceneColors
}) {
  const dashHalfW = 0.014
  const dashThick = 0.002

  const fontSize = 0.033
  // Dashes sit at rulerX (closest to tent). Labels sit to the right (further from tent).
  const labelX = rulerX + 0.04

  const tickColor = colors.frame

  return (
    <group>
      {ticks.map(({ y, isMajor, label }) => {
        const hw = isMajor ? dashHalfW * 1.4 : dashHalfW * 0.6
        return (
          <group key={y}>
            {/* Horizontal tick dash — closest to the tent, extending left. */}
              <mesh
                position={[rulerX - hw, y, rulerZ]}
              >
                <boxGeometry args={[hw * 2, dashThick, tickDepth]} />
                <meshBasicMaterial color={tickColor} />
              </mesh>

            {/* Number label every 10 cm — to the right of dashes, left-aligned. */}
            {label != null ? (
              <Text font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjQ.woff2"
                position={[labelX, y, rulerZ]}
                fontSize={fontSize}
                color={tickColor}
                anchorX="left"
                anchorY="middle"
                outlineWidth={0}
              >
                {label}
              </Text>
            ) : null}
          </group>
        )
      })}
    </group>
  )
}
