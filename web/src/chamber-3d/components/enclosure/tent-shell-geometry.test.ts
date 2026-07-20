import { describe, expect, it } from "vitest"

import { CHAMBER_GEOMETRY } from "@/chamber-3d/core/scene-tokens"
import { buildShellPanels } from "@/chamber-3d/components/enclosure/tent-shell-geometry"

describe("buildShellPanels", () => {
  it("emits five open-front panels (no +Z doorway wall)", () => {
    const panels = buildShellPanels(1.2, 1.0, 2.0)
    expect(panels).toHaveLength(5)
  })

  it("places floor and ceiling on the outer envelope mid-thickness", () => {
    const t = CHAMBER_GEOMETRY.wallThicknessM
    const heightM = 2.0
    const panels = buildShellPanels(1.2, 1.0, heightM, t)
    const floor = panels[0]
    const ceiling = panels[1]
    expect(floor?.position[1]).toBeCloseTo(t / 2, 9)
    expect(ceiling?.position[1]).toBeCloseTo(heightM - t / 2, 9)
  })

  it("keeps left/right/back centers properly inset and heights trimmed by floor/ceiling", () => {
    const widthM = 1.2
    const depthM = 1.0
    const heightM = 2.0
    const t = CHAMBER_GEOMETRY.wallThicknessM
    const panels = buildShellPanels(widthM, depthM, heightM, t)
    const back = panels[2]
    const left = panels[3]
    const right = panels[4]
    expect(back?.position[2]).toBeCloseTo(-depthM / 2 + t / 2, 9)
    expect(left?.position[0]).toBeCloseTo(-widthM / 2 + t / 2, 9)
    expect(right?.position[0]).toBeCloseTo(widthM / 2 - t / 2, 9)
    // Centers are at exactly H/2 because walls sit between t and H-t
    expect(left?.position[1]).toBeCloseTo(heightM / 2, 9)
    expect(right?.position[1]).toBeCloseTo(heightM / 2, 9)
    expect(back?.position[1]).toBeCloseTo(heightM / 2, 9)
  })

  it("trims wall face sizes to perfectly butt against each other without overlapping", () => {
    const widthM = 1.2
    const depthM = 1.0
    const heightM = 2.0
    const t = CHAMBER_GEOMETRY.wallThicknessM
    const panels = buildShellPanels(widthM, depthM, heightM, t)
    const floor = panels[0]
    const back = panels[2]
    const left = panels[3]

    // Floor and ceiling are full size
    expect(floor?.size[0]).toBeCloseTo(widthM, 9)
    expect(floor?.size[1]).toBeCloseTo(depthM, 9)
    // Back wall is tucked inside left/right walls and floor/ceiling
    expect(back?.size[0]).toBeCloseTo(widthM - 2 * t, 9)
    expect(back?.size[1]).toBeCloseTo(heightM - 2 * t, 9)
    // Left wall is tucked between floor and ceiling
    expect(left?.size[0]).toBeCloseTo(depthM, 9) // Full depth
    expect(left?.size[1]).toBeCloseTo(heightM - 2 * t, 9)
  })
})
