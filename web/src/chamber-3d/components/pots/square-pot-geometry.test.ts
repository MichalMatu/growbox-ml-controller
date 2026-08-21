import { describe, expect, it } from "vitest"

import {
  DEFAULT_SQUARE_POT_PRESET_ID,
  SQUARE_POT_COUNT_MAX,
  SQUARE_POT_PRESETS,
  clampSquarePotCount,
  squarePotAspectRatio,
  getSquarePotPreset,
  maxCellsAlong,
  maxSquarePotsThatFit,
  planSquarePotLayout,
  usableFloorM,
} from "@/chamber-3d/components/pots/square-pot-geometry"

describe("square pot presets", () => {
  it("keeps pots near square (side/height in 0.75–1.25)", () => {
    for (const preset of SQUARE_POT_PRESETS) {
      const ratio = squarePotAspectRatio(preset)
      expect(ratio, preset.id).toBeGreaterThanOrEqual(0.75)
      expect(ratio, preset.id).toBeLessThanOrEqual(1.25)
    }
  })

  it("default preset is 12 L", () => {
    const preset = getSquarePotPreset(DEFAULT_SQUARE_POT_PRESET_ID)
    expect(preset.volumeL).toBe(12)
    expect(preset.sideCm).toBe(22)
    expect(preset.heightCm).toBe(24)
  })

  it("volumes are within ±10% of nominal", () => {
    for (const preset of SQUARE_POT_PRESETS) {
      const actual = (preset.sideCm * preset.sideCm * preset.heightCm) / 1000
      const tolerance = preset.volumeL * 0.1
      expect(
        actual,
        `${preset.id}: expected ~${preset.volumeL}L, got ${actual.toFixed(1)}L`
      ).toBeGreaterThanOrEqual(preset.volumeL - tolerance)
      expect(
        actual,
        `${preset.id}: expected ~${preset.volumeL}L, got ${actual.toFixed(1)}L`
      ).toBeLessThanOrEqual(preset.volumeL + tolerance)
    }
  })
})

describe("clampSquarePotCount", () => {
  it("clamps to 0–9", () => {
    expect(clampSquarePotCount(-1)).toBe(0)
    expect(clampSquarePotCount(0)).toBe(0)
    expect(clampSquarePotCount(2.4)).toBe(2)
    expect(clampSquarePotCount(9)).toBe(9)
    expect(clampSquarePotCount(12)).toBe(SQUARE_POT_COUNT_MAX)
    expect(clampSquarePotCount(Number.NaN)).toBe(0)
  })
})

describe("floor packing", () => {
  const pot12 = { sideCm: 22, heightCm: 24 }

  it("maxCellsAlong needs full side for the first pot", () => {
    expect(maxCellsAlong(0.21, 0.22)).toBe(0)
    expect(maxCellsAlong(0.22, 0.22)).toBe(1)
    // two 22 cm pots + 4 cm gap = 48 cm
    expect(maxCellsAlong(0.48, 0.22)).toBe(2)
    expect(maxCellsAlong(0.47, 0.22)).toBe(1)
  })

  it("80×80×160 cm tent fits four 12 L square pots", () => {
    const max = maxSquarePotsThatFit(0.8, 0.8, 1.6, pot12)
    expect(max).toBeGreaterThanOrEqual(4)
    const plan = planSquarePotLayout(0.8, 0.8, 1.6, pot12, 4)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(4)
    expect(plan.positions).toHaveLength(4)
  })

  it("120×120×200 cm tent fits nine 12 L square pots (3×3 grid)", () => {
    const max = maxSquarePotsThatFit(1.2, 1.2, 2.0, pot12)
    expect(max).toBe(9)
    const plan = planSquarePotLayout(1.2, 1.2, 2.0, pot12, 9)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(9)
    expect(plan.positions).toHaveLength(9)
  })

  it("tiny floor fits at most one small pot", () => {
    const max12 = maxSquarePotsThatFit(0.4, 0.4, 1.0, pot12)
    expect(max12).toBeLessThanOrEqual(1)

    const pot7 = { sideCm: 20, heightCm: 18 }
    const max7 = maxSquarePotsThatFit(0.45, 0.45, 1.0, pot7)
    expect(max7).toBeGreaterThanOrEqual(1)
  })

  it("rejects pots taller than the tent", () => {
    const tall = { sideCm: 20, heightCm: 200 }
    expect(maxSquarePotsThatFit(1.2, 1.2, 0.5, tall)).toBe(0)
  })

  it("does not place more pots than fit when more are requested", () => {
    const pot38 = { sideCm: 33, heightCm: 36 }
    const plan = planSquarePotLayout(0.55, 0.55, 1.2, pot38, 4)
    expect(plan.maxFit).toBeLessThanOrEqual(1)
    expect(plan.fittedCount).toBe(plan.maxFit)
    expect(plan.fits).toBe(false)
    expect(plan.positions).toHaveLength(plan.fittedCount)
  })

  it("centers a single pot at the origin", () => {
    const plan = planSquarePotLayout(1.0, 1.0, 1.8, pot12, 1)
    expect(plan.fits).toBe(true)
    expect(plan.positions).toEqual([{ x: 0, z: 0 }])
  })

  it("places two pots along the wider axis without overlapping", () => {
    const plan = planSquarePotLayout(1.2, 0.7, 1.6, pot12, 2)
    expect(plan.fittedCount).toBe(2)
    const [a, b] = plan.positions
    expect(a).toBeDefined()
    expect(b).toBeDefined()
    const dx = Math.abs(a!.x - b!.x)
    const dz = Math.abs(a!.z - b!.z)
    const minCenterDist = 0.22 + 0.04
    expect(Math.hypot(dx, dz)).toBeGreaterThanOrEqual(minCenterDist - 1e-9)
  })

  it("usable floor is smaller than outer envelope", () => {
    const floor = usableFloorM(1.0, 0.8)
    expect(floor.widthM).toBeLessThan(1.0)
    expect(floor.depthM).toBeLessThan(0.8)
    expect(floor.widthM).toBeGreaterThan(0.7)
  })

  it("zero requested yields empty plan that still fits", () => {
    const plan = planSquarePotLayout(0.8, 0.8, 1.6, pot12, 0)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(0)
    expect(plan.positions).toHaveLength(0)
    expect(plan.maxFit).toBeGreaterThanOrEqual(4)
  })
})
