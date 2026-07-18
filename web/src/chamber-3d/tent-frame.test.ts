import { describe, expect, it } from "vitest"

import { CHAMBER_GEOMETRY } from "@/chamber-3d/scene-tokens"
import {
  buildFrameSegments,
  computeFrameCornerBox,
} from "@/chamber-3d/tent-frame-geometry"

function almostEqual(a: number, b: number, eps = 1e-9): boolean {
  return Math.abs(a - b) <= eps
}

function edgeDirection(
  from: readonly [number, number, number],
  to: readonly [number, number, number],
): [number, number, number] {
  const dx = to[0] - from[0]
  const dy = to[1] - from[1]
  const dz = to[2] - from[2]
  const len = Math.hypot(dx, dy, dz)
  expect(len).toBeGreaterThan(1e-8)
  return [dx / len, dy / len, dz / len]
}

function isAxisAligned(dir: readonly [number, number, number]): boolean {
  const abs = dir.map(Math.abs)
  const ones = abs.filter((v) => almostEqual(v, 1)).length
  const zeros = abs.filter((v) => almostEqual(v, 0)).length
  return ones === 1 && zeros === 2
}

function dot(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

describe("computeFrameCornerBox", () => {
  it("uses the same outer inset on X, Y, and Z (top/bottom match sides)", () => {
    const widthM = 1.2
    const depthM = 1.0
    const heightM = 2.0
    const r = CHAMBER_GEOMETRY.frameRadiusM
    const eps = CHAMBER_GEOMETRY.frameContactEpsilonM
    const inset = r + eps

    const box = computeFrameCornerBox(widthM, depthM, heightM, r)

    expect(box.xL).toBeCloseTo(-widthM / 2 + inset, 9)
    expect(box.xR).toBeCloseTo(widthM / 2 - inset, 9)
    expect(box.zBack).toBeCloseTo(-depthM / 2 + inset, 9)
    expect(box.zFront).toBeCloseTo(depthM / 2 - inset, 9)
    // Top/bottom must not use wallThickness — same outer-pocket inset.
    expect(box.yBottom).toBeCloseTo(inset, 9)
    expect(box.yTop).toBeCloseTo(heightM - inset, 9)
    expect(box.yBottom).not.toBeCloseTo(
      CHAMBER_GEOMETRY.wallThicknessM + inset,
      3,
    )
  })

  it("forms a non-degenerate orthotope", () => {
    const box = computeFrameCornerBox(0.8, 0.6, 1.5, 0.018)
    expect(box.xR).toBeGreaterThan(box.xL)
    expect(box.yTop).toBeGreaterThan(box.yBottom)
    expect(box.zFront).toBeGreaterThan(box.zBack)
  })
})

describe("buildFrameSegments", () => {
  it("has 12 edges and every edge is axis-aligned", () => {
    const box = computeFrameCornerBox(1.2, 1.0, 2.0, 0.018)
    const segments = buildFrameSegments(box)
    expect(segments).toHaveLength(12)

    for (const [from, to] of segments) {
      expect(isAxisAligned(edgeDirection(from, to))).toBe(true)
    }
  })

  it("meets at 90° at every corner (three mutually orthogonal edges)", () => {
    const box = computeFrameCornerBox(1.2, 1.0, 2.0, 0.018)
    const segments = buildFrameSegments(box)

    type Key = string
    const keyOf = (p: readonly [number, number, number]): Key =>
      p.map((v) => v.toFixed(9)).join(",")

    const dirsAt = new Map<Key, Array<[number, number, number]>>()

    for (const [from, to] of segments) {
      const dir = edgeDirection(from, to)
      const rev: [number, number, number] = [-dir[0], -dir[1], -dir[2]]
      const fk = keyOf(from)
      const tk = keyOf(to)
      const fl = dirsAt.get(fk) ?? []
      fl.push(dir)
      dirsAt.set(fk, fl)
      const tl = dirsAt.get(tk) ?? []
      tl.push(rev)
      dirsAt.set(tk, tl)
    }

    // 8 orthotope corners, each with exactly 3 edges
    expect(dirsAt.size).toBe(8)

    for (const dirs of dirsAt.values()) {
      expect(dirs).toHaveLength(3)
      // pairwise orthogonal
      expect(Math.abs(dot(dirs[0], dirs[1]))).toBeLessThan(1e-9)
      expect(Math.abs(dot(dirs[0], dirs[2]))).toBeLessThan(1e-9)
      expect(Math.abs(dot(dirs[1], dirs[2]))).toBeLessThan(1e-9)
      // span X, Y, Z (absolute unit axes)
      const axes = dirs.map((d) => d.map(Math.abs).indexOf(1))
      expect(new Set(axes).size).toBe(3)
    }
  })
})
