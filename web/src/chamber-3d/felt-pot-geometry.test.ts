import { describe, expect, it } from "vitest"

import {
  DEFAULT_FELT_POT_PRESET_ID,
  FELT_POT_COUNT_MAX,
  FELT_POT_PRESETS,
  clampFeltPotCount,
  feltPotAspectRatio,
  getFeltPotPreset,
  maxCellsAlong,
  maxPotsThatFit,
  planFeltPotLayout,
  usableFloorM,
} from "@/chamber-3d/felt-pot-geometry"

describe("felt pot presets", () => {
  it("keeps mid-size bags near square (D/H in 0.75–1.25)", () => {
    for (const preset of FELT_POT_PRESETS) {
      const ratio = feltPotAspectRatio(preset)
      expect(ratio, preset.id).toBeGreaterThanOrEqual(0.75)
      expect(ratio, preset.id).toBeLessThanOrEqual(1.25)
    }
  })

  it("default preset is 12 L (golden pot_volume_l)", () => {
    const preset = getFeltPotPreset(DEFAULT_FELT_POT_PRESET_ID)
    expect(preset.volumeL).toBe(12)
    expect(preset.diameterCm).toBe(26)
    expect(preset.heightCm).toBe(24)
  })
})

describe("clampFeltPotCount", () => {
  it("clamps to 0–9", () => {
    expect(clampFeltPotCount(-1)).toBe(0)
    expect(clampFeltPotCount(0)).toBe(0)
    expect(clampFeltPotCount(2.4)).toBe(2)
    expect(clampFeltPotCount(9)).toBe(9)
    expect(clampFeltPotCount(12)).toBe(FELT_POT_COUNT_MAX)
    expect(clampFeltPotCount(Number.NaN)).toBe(0)
  })
})

describe("floor packing", () => {
  const pot12 = { diameterCm: 26, heightCm: 24 }

  it("maxCellsAlong needs full diameter for the first pot", () => {
    expect(maxCellsAlong(0.25, 0.26)).toBe(0)
    expect(maxCellsAlong(0.26, 0.26)).toBe(1)
    // two 26 cm pots + 4 cm gap = 56 cm
    expect(maxCellsAlong(0.56, 0.26)).toBe(2)
    expect(maxCellsAlong(0.55, 0.26)).toBe(1)
  })

  it("80×80×160 cm tent fits four 12 L pots", () => {
    const max = maxPotsThatFit(0.8, 0.8, 1.6, pot12)
    expect(max).toBe(4)
    const plan = planFeltPotLayout(0.8, 0.8, 1.6, pot12, 4)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(4)
    expect(plan.positions).toHaveLength(4)
  })

  it("120×120×200 cm tent fits nine 12 L pots (3×3 grid)", () => {
    const max = maxPotsThatFit(1.2, 1.2, 2.0, pot12)
    expect(max).toBe(9)
    const plan = planFeltPotLayout(1.2, 1.2, 2.0, pot12, 9)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(9)
    expect(plan.positions).toHaveLength(9)
  })

  it("tiny floor fits at most one small pot", () => {
    // 40 cm tent, usable shrinks by wall/frame/margin — may be zero for 26 cm
    const max12 = maxPotsThatFit(0.4, 0.4, 1.0, pot12)
    expect(max12).toBeLessThanOrEqual(1)

    const pot7 = { diameterCm: 20, heightCm: 18 }
    const max7 = maxPotsThatFit(0.45, 0.45, 1.0, pot7)
    expect(max7).toBeGreaterThanOrEqual(1)
  })

  it("rejects pots taller than the tent", () => {
    const tall = { diameterCm: 20, heightCm: 200 }
    expect(maxPotsThatFit(1.2, 1.2, 0.5, tall)).toBe(0)
  })

  it("does not place more pots than fit when more are requested", () => {
    // Force a floor that holds only one 38 L pot
    const pot38 = { diameterCm: 37, heightCm: 36 }
    const plan = planFeltPotLayout(0.55, 0.55, 1.2, pot38, 4)
    expect(plan.maxFit).toBeLessThanOrEqual(1)
    expect(plan.fittedCount).toBe(plan.maxFit)
    expect(plan.fits).toBe(false)
    expect(plan.positions).toHaveLength(plan.fittedCount)
  })

  it("centers a single pot at the origin", () => {
    const plan = planFeltPotLayout(1.0, 1.0, 1.8, pot12, 1)
    expect(plan.fits).toBe(true)
    expect(plan.positions).toEqual([{ x: 0, z: 0 }])
  })

  it("places two pots along the wider axis without overlapping", () => {
    const plan = planFeltPotLayout(1.2, 0.7, 1.6, pot12, 2)
    expect(plan.fittedCount).toBe(2)
    const [a, b] = plan.positions
    expect(a).toBeDefined()
    expect(b).toBeDefined()
    const dx = Math.abs(a!.x - b!.x)
    const dz = Math.abs(a!.z - b!.z)
    const minCenterDist = 0.26 + 0.04
    expect(Math.hypot(dx, dz)).toBeGreaterThanOrEqual(minCenterDist - 1e-9)
  })

  it("usable floor is smaller than outer envelope", () => {
    const floor = usableFloorM(1.0, 0.8)
    expect(floor.widthM).toBeLessThan(1.0)
    expect(floor.depthM).toBeLessThan(0.8)
    expect(floor.widthM).toBeGreaterThan(0.7)
  })

  it("zero requested yields empty plan that still fits", () => {
    const plan = planFeltPotLayout(0.8, 0.8, 1.6, pot12, 0)
    expect(plan.fits).toBe(true)
    expect(plan.fittedCount).toBe(0)
    expect(plan.positions).toHaveLength(0)
    expect(plan.maxFit).toBe(4)
  })
})
