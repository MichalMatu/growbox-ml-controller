import { describe, expect, it } from "vitest"

import {
  clampEnclosureCm,
  commitEnclosureCm,
  ENCLOSURE_CM_MAX,
  ENCLOSURE_CM_MIN,
  isLiveEnclosureCm,
  parseEnclosureCmDraft,
} from "@/chamber-3d/components/enclosure/enclosure-cm"

describe("enclosure cm bounds", () => {
  it("clamps to 40–500", () => {
    expect(clampEnclosureCm(10)).toBe(ENCLOSURE_CM_MIN)
    expect(clampEnclosureCm(39)).toBe(ENCLOSURE_CM_MIN)
    expect(clampEnclosureCm(40)).toBe(40)
    expect(clampEnclosureCm(120)).toBe(120)
    expect(clampEnclosureCm(500)).toBe(ENCLOSURE_CM_MAX)
    expect(clampEnclosureCm(999)).toBe(ENCLOSURE_CM_MAX)
  })

  it("parses drafts without clamping intermediate typing", () => {
    expect(parseEnclosureCmDraft("")).toBeNull()
    expect(parseEnclosureCmDraft("  ")).toBeNull()
    expect(parseEnclosureCmDraft("1")).toBe(1)
    expect(parseEnclosureCmDraft("12")).toBe(12)
    expect(parseEnclosureCmDraft("120")).toBe(120)
    expect(parseEnclosureCmDraft("abc")).toBeNull()
  })

  it("only marks in-range values as live preview", () => {
    expect(isLiveEnclosureCm(1)).toBe(false)
    expect(isLiveEnclosureCm(39)).toBe(false)
    expect(isLiveEnclosureCm(40)).toBe(true)
    expect(isLiveEnclosureCm(500)).toBe(true)
    expect(isLiveEnclosureCm(501)).toBe(false)
  })

  it("commits with round + clamp and keeps fallback on empty", () => {
    expect(commitEnclosureCm("", 80)).toBe(80)
    expect(commitEnclosureCm("10", 80)).toBe(ENCLOSURE_CM_MIN)
    expect(commitEnclosureCm("45.6", 80)).toBe(46)
    expect(commitEnclosureCm("600", 80)).toBe(ENCLOSURE_CM_MAX)
  })
})
