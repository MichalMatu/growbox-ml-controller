import { useEffect, useMemo } from "react"
import { BoxGeometry, MeshStandardMaterial } from "three"

import {
  CHAMBER_MATERIAL,
  type ChamberSceneColors,
} from "@/chamber-3d/core/scene-tokens"
import { RoomWallRuler } from "@/chamber-3d/components/enclosure/back-wall-ruler"

export type RoomLayout = "none" | "flat" | "corner"

export type RoomProps = {
  layout: RoomLayout
  colors: ChamberSceneColors
  tentHalfM: { width: number; depth: number; height: number }
  /** Room wall height in meters (from cm input, clamped 40–500). */
  wallHeightM: number
}

/* ── constants (meters) ── */

const T = 0.12 // wall thickness
const Bh = 0.08 // baseboard height
const Bd = 0.015 // baseboard depth
const G = Bd + 0.01 // tent → wall inner face gap ≈ 2.5 cm
const E = 1.5 // extra wall beyond tent on open side

/* ── helpers ── */

/** Inner face position (faces tent). */
function inner(tentHalf: number): number {
  return -(tentHalf + G)
}

/** Outer face position (away from tent). */
function outer(tentHalf: number): number {
  return -(tentHalf + G + T)
}

/** Wall centre (mid-thickness). */
function centre(tentHalf: number): number {
  return -(tentHalf + G + T / 2)
}

/**
 * Room with thick walls (12 cm).
 *
 * Flat:   single back wall behind tent, centred on X.
 * Corner: back wall (-Z) + left wall (-X) forming a solid L.
 *   Each wall extends to the OUTER face of the other wall —
 *   classic construction join where framing overlaps in the corner.
 *   No gaps, no crossing — the back wall runs the full width,
 *   the left wall's back edge sits behind the back wall inner face.
 */
export function Room({ layout, colors, tentHalfM, wallHeightM }: RoomProps) {
  if (layout === "none") return null

  const hx = tentHalfM.width
  const hz = tentHalfM.depth

  if (layout === "flat") {
    const w = (hx + E) * 2
    const wallInnerZ = inner(hz)
    const wallCz = centre(hz)
    const wallLeftX = -w / 2
    return (
      <group>
        <Floor c={colors} />
        <WallBox w={w} cx={0} cz={wallCz} wallHeightM={wallHeightM} c={colors} />
        <BBx s={wallLeftX} l={w} face={wallInnerZ} c={colors} />
        <RoomWallRuler
          wallHeightM={wallHeightM}
          wallInnerZ={wallInnerZ}
          tentRightX={hx}
          colors={colors}
        />
      </group>
    )
  }

  /* ── corner L ── */

  // Back wall: spans X from left-wall outer face to past tent right edge.
  const bwX0 = outer(hx) // left-wall outer face
  const bwX1 = hx + E // right past tent
  const bwW = bwX1 - bwX0
  const bwCx = (bwX0 + bwX1) / 2
  const bwCz = centre(hz)

  // Left wall: spans Z from back-wall outer face (full embed) to past tent front edge.
  const lwZ0 = outer(hz) // both walls share the exterior corner
  const lwZ1 = hz + E // front past tent
  const lwL = lwZ1 - lwZ0
  const lwCx = centre(hx)
  const lwCz = (lwZ0 + lwZ1) / 2

  // Baseboard inner face positions
  const bIFace = inner(hz) // Z of back wall inner face
  const sIFace = inner(hx) // X of left wall inner face

  return (
    <group>
      <Floor c={colors} />
      <WallBox w={bwW} cx={bwCx} cz={bwCz} wallHeightM={wallHeightM} c={colors} />
      <WallBox w={lwL} cx={lwCx} cz={lwCz} rot wallHeightM={wallHeightM} c={colors} />
      {/* Baseboard on back wall: from left-wall inner face to right end */}
      <BBx s={sIFace} l={bwX1 - sIFace} face={bIFace} c={colors} />
      {/* Baseboard on left wall: from back-wall inner face to front end */}
      <BBz s={bIFace} l={lwZ1 - bIFace} face={sIFace} c={colors} />
      <RoomWallRuler
        wallHeightM={wallHeightM}
        wallInnerZ={bIFace}
        tentRightX={hx}
        colors={colors}
      />
    </group>
  )
}

/* ── floor ── */

function Floor({ c }: { c: ChamberSceneColors }) {
  const m = useMemo(
    () => new MeshStandardMaterial({ color: c.roomFloor, roughness: CHAMBER_MATERIAL.roomFloorRoughness, metalness: CHAMBER_MATERIAL.roomFloorMetalness }),
    [c.roomFloor],
  )
  useEffect(() => { return () => m.dispose() }, [m])
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow material={m}>
      <planeGeometry args={[12, 12]} />
    </mesh>
  )
}

/* ── wall BoxGeometry ── */

function WallBox({
  w, cx, cz, rot, wallHeightM, c,
}: {
  w: number
  cx: number // wall X centre (unrotated)
  cz: number // wall Z centre (unrotated); rot swaps axis meaning
  rot?: boolean
  wallHeightM: number
  c: ChamberSceneColors
}) {
  const g = useMemo(() => new BoxGeometry(w, wallHeightM, T), [w, wallHeightM])
  const m = useMemo(
    () => new MeshStandardMaterial({ color: c.roomWall, roughness: CHAMBER_MATERIAL.roomWallRoughness, metalness: CHAMBER_MATERIAL.roomWallMetalness }),
    [c.roomWall],
  )
  const fm = useMemo(() => [m, m, m, m, m, m], [m])
  useEffect(() => { return () => { g.dispose(); m.dispose() } }, [g, m])

  // Unrotated: BoxGeometry(w, wallHeightM, T) → X span = w, Z span = T.
  // Rotated 90° around Y: X span = T, Z span = w.
  const pos: [number, number, number] = rot
    ? [cx, wallHeightM / 2, cz]
    : [cx, wallHeightM / 2, cz]
  const r: [number, number, number] = rot ? [0, Math.PI / 2, 0] : [0, 0, 0]
  return <mesh geometry={g} material={fm} position={pos} rotation={r} castShadow receiveShadow />
}

/* ── baseboard strips ── */

function BBx({ s, l, face, c }: { s: number; l: number; face: number; c: ChamberSceneColors }) {
  const m = useMemo(
    () => new MeshStandardMaterial({ color: c.roomBaseboard, roughness: CHAMBER_MATERIAL.roomBaseboardRoughness, metalness: CHAMBER_MATERIAL.roomBaseboardMetalness }),
    [c.roomBaseboard],
  )
  useEffect(() => { return () => m.dispose() }, [m])
  return (
    <mesh position={[s + l / 2, Bh / 2, face + Bd / 2]} material={m} castShadow receiveShadow>
      <boxGeometry args={[l, Bh, Bd]} />
    </mesh>
  )
}

function BBz({ s, l, face, c }: { s: number; l: number; face: number; c: ChamberSceneColors }) {
  const m = useMemo(
    () => new MeshStandardMaterial({ color: c.roomBaseboard, roughness: CHAMBER_MATERIAL.roomBaseboardRoughness, metalness: CHAMBER_MATERIAL.roomBaseboardMetalness }),
    [c.roomBaseboard],
  )
  useEffect(() => { return () => m.dispose() }, [m])
  return (
    <mesh position={[face + Bd / 2, Bh / 2, s + l / 2]} material={m} castShadow receiveShadow>
      <boxGeometry args={[Bd, Bh, l]} />
    </mesh>
  )
}
