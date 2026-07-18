import { describe, expect, it } from "vitest"

import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"
import {
  buildRearFlapZippers,
  buildZipperRectSegments,
} from "@/chamber-3d/tent-vent-geometry"

describe("buildZipperRectSegments", () => {
  it("forms a closed rectangle including the top rail", () => {
    const [left, bottom, right, top] = buildZipperRectSegments(0.3, 0.2)
    expect(left[0][1]).toBeGreaterThan(left[1][1])
    expect(bottom[1][0]).toBeGreaterThan(bottom[0][0])
    expect(right[1][1]).toBeGreaterThan(right[0][1])
    expect(top[0][1]).toBeCloseTo(top[1][1], 9)
    expect(top[0][1]).toBeCloseTo(0.1, 9)
    expect(top[0][0]).toBeGreaterThan(top[1][0])
  })
})

describe("buildRearFlapZippers", () => {
  it("uses fixed 30×20 cm size with bottom edge 20 cm from the floor", () => {
    const widthM = 1.2
    const depthM = 1.0
    const heightM = 2.0
    const t = CHAMBER_GEOMETRY.wallThicknessM
    const zippers = buildRearFlapZippers(widthM, depthM, heightM, t)
    expect(zippers).toHaveLength(2)

    const interior = zippers.find((z) => z.face === "interior")
    const exterior = zippers.find((z) => z.face === "exterior")
    expect(interior).toBeDefined()
    expect(exterior).toBeDefined()
    if (!interior || !exterior) return

    expect(interior.size[0]).toBeCloseTo(0.3, 9)
    expect(interior.size[1]).toBeCloseTo(0.2, 9)
    // Center = 20 cm bottom + half of 20 cm height = 30 cm
    expect(interior.position[1]).toBeCloseTo(0.3, 9)
    expect(exterior.position[1]).toBeCloseTo(0.3, 9)

    const offset = CHAMBER_GEOMETRY.rearFlapOutlineOffsetM
    expect(interior.position[2]).toBeCloseTo(-depthM / 2 + t + offset, 9)
    expect(exterior.position[2]).toBeCloseTo(-depthM / 2 - offset, 9)
  })

  it("returns empty when the fixed flap does not fit the face", () => {
    const zippers = buildRearFlapZippers(0.25, 0.25, 0.4)
    expect(zippers).toEqual([])
  })

  it("returns empty when height is too short for 20 cm lift + 20 cm flap", () => {
    // bottom 0.2 + height 0.2 = 0.4 top; corner clearance leaves less room
    const zippers = buildRearFlapZippers(1.0, 1.0, 0.35)
    expect(zippers).toEqual([])
  })
})
