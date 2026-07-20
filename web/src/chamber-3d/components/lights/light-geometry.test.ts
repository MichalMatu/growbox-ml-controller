import { describe, expect, it } from "vitest"

import {
  DEFAULT_LIGHT_CEILING_GAP_CM,
  LIGHT_CEILING_GAP_MIN_CM,
  LIGHT_FLOOR_CLEARANCE_MIN_CM,
  clampCeilingGapCm,
  getLightPreset,
  listFittingOrientations,
  maxCeilingGapCm,
  orientedFootprintCm,
  planLightFit,
  resolveLightOrientationDeg,
} from "@/chamber-3d/components/lights/light-geometry"

describe("light-geometry", () => {
  it("swaps footprint axes at 90° orientation", () => {
    const led = getLightPreset("led_bar_100")
    const alongWidth = orientedFootprintCm(led, 0)
    const alongDepth = orientedFootprintCm(led, 90)
    expect(alongWidth.extentXCm).toBe(100)
    expect(alongWidth.extentZCm).toBe(12)
    expect(alongDepth.extentXCm).toBe(12)
    expect(alongDepth.extentZCm).toBe(100)
  })

  it("fits a 60×60 LED in an 80×80×160 tent", () => {
    const preset = getLightPreset("led_board_60")
    const plan = planLightFit(0.8, 0.8, 1.6, preset, 0, DEFAULT_LIGHT_CEILING_GAP_CM)
    expect(plan.fits).toBe(true)
    expect(plan.placement).not.toBeNull()
    expect(plan.placement!.y).toBeGreaterThan(0.5)
  })

  it("rejects a 90×80 LED in a narrow 80 cm tent", () => {
    const preset = getLightPreset("led_board_90")
    const plan = planLightFit(0.8, 0.8, 1.6, preset, 0, DEFAULT_LIGHT_CEILING_GAP_CM)
    expect(plan.fitsHorizontal).toBe(false)
    expect(plan.fits).toBe(false)
    expect(plan.placement).toBeNull()
  })

  it("allows a long bar when rotated to match depth", () => {
    // 120×40 floor: bar 100×12 along X fits; along Z needs depth ≥ 100.
    const preset = getLightPreset("led_bar_100")
    const alongX = planLightFit(1.2, 0.4, 1.6, preset, 0, 5)
    const alongZ = planLightFit(1.2, 0.4, 1.6, preset, 90, 5)
    expect(alongX.fitsHorizontal).toBe(true)
    expect(alongZ.fitsHorizontal).toBe(false)
  })

  it("clamps ceiling gap so body stays above floor clearance", () => {
    const bodyH = 22
    const tentH = 1.0
    const maxGap = maxCeilingGapCm(tentH, bodyH)
    expect(maxGap).toBeGreaterThanOrEqual(LIGHT_CEILING_GAP_MIN_CM)
    const huge = clampCeilingGapCm(500, tentH, bodyH)
    expect(huge).toBe(maxGap)
    const tiny = clampCeilingGapCm(0, tentH, bodyH)
    expect(tiny).toBe(LIGHT_CEILING_GAP_MIN_CM)
  })

  it("none preset always fits with no placement", () => {
    const plan = planLightFit(0.5, 0.5, 0.5, getLightPreset("none"), 0, 5)
    expect(plan.fits).toBe(true)
    expect(plan.placement).toBeNull()
  })

  it("vertical fit respects floor clearance constant", () => {
    // Very short tent: body + floor clearance cannot fit.
    const preset = getLightPreset("hps_box_1000")
    const plan = planLightFit(1.2, 1.2, 0.5, preset, 0, LIGHT_CEILING_GAP_MIN_CM)
    expect(plan.fitsVertical).toBe(false)
    expect(LIGHT_FLOOR_CLEARANCE_MIN_CM).toBe(40)
  })

  it("90×80 LED fits 120×90 tent in only one orientation", () => {
    const preset = getLightPreset("led_board_90")
    // length×width = 90×80; tent W×D = 120×90
    const at0 = planLightFit(1.2, 0.9, 1.6, preset, 0, 5)
    const at90 = planLightFit(1.2, 0.9, 1.6, preset, 90, 5)
    const fitting = listFittingOrientations(1.2, 0.9, 1.6, preset, 5)

    expect(at0.fitsHorizontal).toBe(true)
    expect(at90.fitsHorizontal).toBe(false)
    expect(fitting).toEqual([0])
    expect(resolveLightOrientationDeg(1.2, 0.9, 1.6, preset, 90, 5)).toBe(0)
    expect(resolveLightOrientationDeg(1.2, 0.9, 1.6, preset, 0, 5)).toBe(0)
  })
})
