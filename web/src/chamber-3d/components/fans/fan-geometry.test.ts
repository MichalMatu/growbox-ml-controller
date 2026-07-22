import { describe, expect, it } from "vitest"
import {
  getFanPreset,
  orientedFanFootprintCm,
  planFanFit,
  clampFanCeilingGapCm,
  maxFanCeilingGapCm,
  listFittingFanOrientations,
  DEFAULT_FAN_CEILING_GAP_CM,
  FAN_CEILING_GAP_MIN_CM,
  type FanPresetId,
  type LightAABB,
} from "./fan-geometry"

// ---- Preset lookup ----

describe("getFanPreset", () => {
  it("returns the requested preset", () => {
    const preset = getFanPreset("fan_125")
    expect(preset.ductDiameterCm).toBe(12.5)
    expect(preset.bodyDiameterCm).toBe(14.5)
  })

  it("falls back to default for unknown id", () => {
    const preset = getFanPreset("nonexistent" as FanPresetId)
    expect(preset.id).toBe("none")
  })

  it('returns "none" preset with zero sizes', () => {
    const preset = getFanPreset("none")
    expect(preset.form).toBe("none")
    expect(preset.totalLengthCm).toBe(0)
  })
})

// ---- Footprint ----

describe("orientedFanFootprintCm", () => {
  it("maps total length to Z at 0° (visual length along Z)", () => {
    const preset = getFanPreset("fan_125")
    const footprint = orientedFanFootprintCm(preset, 0)
    expect(footprint.extentXCm).toBe(preset.bodyDiameterCm)
    expect(footprint.extentZCm).toBe(preset.totalLengthCm)
  })

  it("maps total length to X at 90° (visual length along X)", () => {
    const preset = getFanPreset("fan_125")
    const footprint = orientedFanFootprintCm(preset, 90)
    expect(footprint.extentXCm).toBe(preset.totalLengthCm)
    expect(footprint.extentZCm).toBe(preset.bodyDiameterCm)
  })

  it("returns zero footprint for none preset", () => {
    const preset = getFanPreset("none")
    const footprint = orientedFanFootprintCm(preset, 0)
    expect(footprint.extentXCm).toBe(0)
    expect(footprint.extentZCm).toBe(0)
  })
})

// ---- Ceiling gap ----

describe("clampFanCeilingGapCm", () => {
  const tentHeightM = 1.6
  const bodyDiameterCm = 14.5 // fan_125

  it("clamps below minimum", () => {
    expect(clampFanCeilingGapCm(1, tentHeightM, bodyDiameterCm)).toBe(FAN_CEILING_GAP_MIN_CM)
  })

  it("clamps above maximum", () => {
    const maxGap = maxFanCeilingGapCm(tentHeightM, bodyDiameterCm)
    expect(clampFanCeilingGapCm(999, tentHeightM, bodyDiameterCm)).toBe(maxGap)
  })

  it("returns exact value when within range", () => {
    expect(clampFanCeilingGapCm(DEFAULT_FAN_CEILING_GAP_CM, tentHeightM, bodyDiameterCm)).toBe(DEFAULT_FAN_CEILING_GAP_CM)
  })

  it("handles non-finite input", () => {
    expect(clampFanCeilingGapCm(NaN, tentHeightM, bodyDiameterCm)).toBe(DEFAULT_FAN_CEILING_GAP_CM)
  })
})

// ---- Fit in tent (no light) ----

describe("planFanFit without light", () => {
  const defaultTent = { widthM: 0.8, depthM: 0.8, heightM: 1.6 }

  it("fits a fan_125 in default 80×80×160 tent", () => {
    const preset = getFanPreset("fan_125")
    const plan = planFanFit(
      defaultTent.widthM,
      defaultTent.depthM,
      defaultTent.heightM,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      null,
    )
    expect(plan.fits).toBe(true)
    expect(plan.placement).not.toBeNull()
    expect(plan.reason).toBeNull()
  })

  it("fits fan_100 (smallest) easily", () => {
    const preset = getFanPreset("fan_100")
    const plan = planFanFit(
      defaultTent.widthM,
      defaultTent.depthM,
      defaultTent.heightM,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      null,
    )
    expect(plan.fits).toBe(true)
  })

  it("rejects fan_200 in a very narrow 30 cm tent", () => {
    const preset = getFanPreset("fan_200")
    const plan = planFanFit(
      0.3,
      0.3,
      1.6,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      null,
    )
    expect(plan.fits).toBe(false)
    expect(plan.fitsHorizontal).toBe(false)
    expect(plan.reason).toContain("poziomo")
  })

  it("rejects any fan in a very short 50 cm tent", () => {
    const preset = getFanPreset("fan_125")
    const plan = planFanFit(
      0.8,
      0.8,
      0.5,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      null,
    )
    expect(plan.fits).toBe(false)
    expect(plan.fitsVertical).toBe(false)
  })

  it("returns true for none preset regardless of tent size", () => {
    const preset = getFanPreset("none")
    const plan = planFanFit(0.1, 0.1, 0.1, preset, 0, DEFAULT_FAN_CEILING_GAP_CM, null)
    expect(plan.fits).toBe(true)
    expect(plan.placement).toBeNull()
  })

  it("placement Y is near the ceiling", () => {
    const preset = getFanPreset("fan_125")
    const plan = planFanFit(
      0.8,
      0.8,
      1.6,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      null,
    )
    expect(plan.placement).not.toBeNull()
    // Fan center should be below the inner ceiling, roughly at heightM - inset - gap - bodyRadius
    expect(plan.placement!.y).toBeGreaterThan(1.0)
    expect(plan.placement!.y).toBeLessThan(1.6)
  })
})

// ---- Collision with light ----

describe("planFanFit with light collision", () => {
  it("always places fan even when light overlaps — light gets pushed down in scene", () => {
    const preset = getFanPreset("fan_125")
    const light: LightAABB = {
      centerX: 0,
      centerY: 0.6,
      centerZ: 0,
      extentXM: 0.6,
      extentZM: 0.6,
      heightM: 0.08,
    }
    const plan = planFanFit(
      0.8,
      0.8,
      1.6,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      light,
    )
    expect(plan.fits).toBe(true)
    expect(plan.placement).not.toBeNull()
  })

  it("fits fan_100 next to a large light in a wider tent", () => {
    const preset = getFanPreset("fan_100") // 20 cm total length
    const light: LightAABB = {
      centerX: 0,
      centerY: 0.6,
      centerZ: 0,
      extentXM: 0.6,
      extentZM: 0.6,
      heightM: 0.08,
    }
    const plan = planFanFit(
      1.2, // wide tent
      1.2,
      2.0,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      light,
    )
    expect(plan.fits).toBe(true)
    expect(plan.placement).not.toBeNull()
  })

  it("fan still fits when light is large — light will be pushed down in scene", () => {
    const preset = getFanPreset("fan_125")
    const light: LightAABB = {
      centerX: 0,
      centerY: 0.6,
      centerZ: 0,
      extentXM: 0.76,
      extentZM: 0.76,
      heightM: 0.08,
    }
    const plan = planFanFit(
      0.8,
      0.8,
      1.6,
      preset,
      0,
      DEFAULT_FAN_CEILING_GAP_CM,
      light,
    )
    // Fan always fits — light gets pushed down in the scene rendering
    expect(plan.fits).toBe(true)
    expect(plan.placement).not.toBeNull()
  })

  it("fits multiple orientations in a roomy tent", () => {
    const preset = getFanPreset("fan_125")
    const orientations = listFittingFanOrientations(
      1.5,
      1.5,
      2.0,
      preset,
      DEFAULT_FAN_CEILING_GAP_CM,
    )
    expect(orientations.length).toBe(2)
    expect(orientations).toContain(0)
    expect(orientations).toContain(90)
  })

  it("only fits one orientation in a very narrow tent", () => {
    const preset = getFanPreset("fan_125")
    // 22 cm total length along Z at 0°, 14.5 body diam along X at 0°
    // Tent: 25 cm wide, 60 cm deep (usable ~17 cm width after margines)
    const orientations = listFittingFanOrientations(
      0.25,
      0.6,
      1.6,
      preset,
      DEFAULT_FAN_CEILING_GAP_CM,
    )
    // Orientation 0°: extentX = 14.5 (body), extentZ = 22 → extentZ 22 <= 52 → fits
    // Orientation 90°: extentX = 22, extentZ = 14.5 → extentX 22 > 17 → won't fit
    expect(orientations.length).toBe(1)
    expect(orientations[0]).toBe(0)
  })
})
