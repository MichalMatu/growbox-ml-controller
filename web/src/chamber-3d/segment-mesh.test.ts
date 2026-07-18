import { describe, expect, it } from "vitest"

import { orientSegmentBetween } from "@/chamber-3d/segment-mesh"

describe("orientSegmentBetween", () => {
  it("places a unit Y segment at the midpoint with full length", () => {
    const { position, length } = orientSegmentBetween([0, 0, 0], [0, 1, 0])
    expect(length).toBeCloseTo(1, 9)
    expect(position[0]).toBeCloseTo(0, 9)
    expect(position[1]).toBeCloseTo(0.5, 9)
    expect(position[2]).toBeCloseTo(0, 9)
  })

  it("returns zero length for coincident points", () => {
    const { length } = orientSegmentBetween([1, 2, 3], [1, 2, 3])
    expect(length).toBe(0)
  })
})
