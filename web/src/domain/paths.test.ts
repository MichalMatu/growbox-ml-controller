import { describe, expect, it } from "vitest"

import { getValueAtPath, setValueAtPath } from "./paths"

describe("schema path helpers", () => {
  it("reads and writes numeric pot segments as array indices", () => {
    const configuration = setValueAtPath({}, "pots.0.irrigation.available", true)
    expect(Array.isArray(configuration.pots)).toBe(true)
    expect(getValueAtPath(configuration, "pots.0.irrigation.available")).toBe(true)
    expect(getValueAtPath(configuration, "pots.1.irrigation.available")).toBeUndefined()
  })

  it("does not mutate the previous root when setting a path", () => {
    const original = setValueAtPath({}, "environment.growbox_volume_m3", 0.8)
    const next = setValueAtPath(original, "environment.growbox_volume_m3", 1.2)
    expect(getValueAtPath(original, "environment.growbox_volume_m3")).toBe(0.8)
    expect(getValueAtPath(next, "environment.growbox_volume_m3")).toBe(1.2)
  })
})
