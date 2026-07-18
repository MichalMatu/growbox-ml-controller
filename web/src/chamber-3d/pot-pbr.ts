/**
 * Procedural PBR maps for felt grow bags + soil (no external assets).
 * Generates albedo / normal / roughness once; materials tint albedo via color.
 */

import { useMemo } from "react"
import {
  CanvasTexture,
  LinearFilter,
  LinearMipmapLinearFilter,
  NoColorSpace,
  RepeatWrapping,
  SRGBColorSpace,
  type Texture,
} from "three"

import { CHAMBER_MATERIAL } from "@/chamber-3d/scene-tokens"

export type PotSurfaceMaps = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
}

export type PotPbrMaps = {
  felt: PotSurfaceMaps
  soil: PotSurfaceMaps
}

function hash2(x: number, y: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123
  return s - Math.floor(s)
}

function smoothNoise(x: number, y: number): number {
  const x0 = Math.floor(x)
  const y0 = Math.floor(y)
  const fx = x - x0
  const fy = y - y0
  const ux = fx * fx * (3 - 2 * fx)
  const uy = fy * fy * (3 - 2 * fy)
  const a = hash2(x0, y0)
  const b = hash2(x0 + 1, y0)
  const c = hash2(x0, y0 + 1)
  const d = hash2(x0 + 1, y0 + 1)
  return (
    a * (1 - ux) * (1 - uy) +
    b * ux * (1 - uy) +
    c * (1 - ux) * uy +
    d * ux * uy
  )
}

/** Fractal value noise in 0..1 */
function fbm(x: number, y: number, octaves: number): number {
  let value = 0
  let amp = 0.5
  let freq = 1
  let norm = 0
  for (let i = 0; i < octaves; i++) {
    value += amp * smoothNoise(x * freq, y * freq)
    norm += amp
    amp *= 0.5
    freq *= 2
  }
  return value / norm
}

function configureMap(texture: Texture, isColor: boolean, repeat: number): void {
  texture.colorSpace = isColor ? SRGBColorSpace : NoColorSpace
  texture.wrapS = RepeatWrapping
  texture.wrapT = RepeatWrapping
  texture.repeat.set(repeat, repeat)
  texture.magFilter = LinearFilter
  texture.minFilter = LinearMipmapLinearFilter
  texture.generateMipmaps = true
  texture.anisotropy = 8
  texture.needsUpdate = true
}

function heightToNormal(
  heights: Float32Array,
  size: number,
  strength: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = y * size + x
      const hL = heights[y * size + ((x - 1 + size) % size)]!
      const hR = heights[y * size + ((x + 1) % size)]!
      const hD = heights[((y - 1 + size) % size) * size + x]!
      const hU = heights[((y + 1) % size) * size + x]!
      let nx = (hL - hR) * strength
      let ny = (hD - hU) * strength
      let nz = 1
      const len = Math.hypot(nx, ny, nz) || 1
      nx /= len
      ny /= len
      nz /= len
      const o = i * 4
      out[o] = Math.round((nx * 0.5 + 0.5) * 255)
      out[o + 1] = Math.round((ny * 0.5 + 0.5) * 255)
      out[o + 2] = Math.round((nz * 0.5 + 0.5) * 255)
      out[o + 3] = 255
    }
  }
  return out
}

function canvasFromRgba(size: number, data: Uint8ClampedArray): HTMLCanvasElement {
  const canvas = document.createElement("canvas")
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext("2d")
  if (!ctx) throw new Error("2d canvas unavailable for pot PBR")
  // Copy into a fresh buffer so ImageData accepts ArrayBuffer (not SharedArrayBuffer).
  const pixels = new Uint8ClampedArray(data.length)
  pixels.set(data)
  ctx.putImageData(new ImageData(pixels, size, size), 0, 0)
  return canvas
}

function buildFeltMaps(size: number): PotSurfaceMaps {
  const heights = new Float32Array(size * size)
  const albedo = new Uint8ClampedArray(size * size * 4)
  const rough = new Uint8ClampedArray(size * size * 4)

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size
      const v = y / size
      // Nonwoven felt: fine fiber flecks + soft low-frequency undulation
      const fibers = fbm(u * 48, v * 48, 5)
      const weave = fbm(u * 12 + 3.1, v * 12 - 1.7, 3)
      const fleck = hash2(x * 0.37, y * 0.91)
      const h =
        fibers * 0.55 + weave * 0.35 + (fleck > 0.92 ? 0.25 : fleck * 0.08)
      heights[y * size + x] = h

      // Multiplier map (grayscale) so material.color tints the bag
      const lum = 0.62 + fibers * 0.28 + weave * 0.12 - (fleck > 0.94 ? 0.18 : 0)
      const c = Math.max(0, Math.min(255, Math.round(lum * 255)))
      const ai = (y * size + x) * 4
      albedo[ai] = c
      albedo[ai + 1] = c
      albedo[ai + 2] = c
      albedo[ai + 3] = 255

      const r = 0.88 + fibers * 0.1 + (fleck > 0.9 ? 0.05 : 0)
      const rv = Math.max(0, Math.min(255, Math.round(r * 255)))
      rough[ai] = rv
      rough[ai + 1] = rv
      rough[ai + 2] = rv
      rough[ai + 3] = 255
    }
  }

  const normal = heightToNormal(heights, size, 4.2)
  const map = new CanvasTexture(canvasFromRgba(size, albedo))
  const normalMap = new CanvasTexture(canvasFromRgba(size, normal))
  const roughnessMap = new CanvasTexture(canvasFromRgba(size, rough))
  configureMap(map, true, CHAMBER_MATERIAL.potFeltUvRepeat)
  configureMap(normalMap, false, CHAMBER_MATERIAL.potFeltUvRepeat)
  configureMap(roughnessMap, false, CHAMBER_MATERIAL.potFeltUvRepeat)
  return { map, normalMap, roughnessMap }
}

function buildSoilMaps(size: number): PotSurfaceMaps {
  const heights = new Float32Array(size * size)
  const albedo = new Uint8ClampedArray(size * size * 4)
  const rough = new Uint8ClampedArray(size * size * 4)

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size
      const v = y / size
      // Soil: clumpy low freq + fine grit + occasional pebbles
      const clump = fbm(u * 6, v * 6, 4)
      const grit = fbm(u * 40, v * 40, 3)
      const pebble = hash2(x * 1.9, y * 2.3)
      const pebbleMask = pebble > 0.97 ? 1 : 0
      const h =
        clump * 0.55 + grit * 0.35 + pebbleMask * 0.45 + hash2(x, y) * 0.08
      heights[y * size + x] = h

      // Brownish variation (rgb numbers — multiplies / replaces flat soil tint)
      const baseR = 48
      const baseG = 32
      const baseB = 18
      const shade = 0.55 + clump * 0.45 + grit * 0.2 - pebbleMask * 0.25
      const r = Math.max(
        0,
        Math.min(255, Math.round((baseR + grit * 35 + pebbleMask * 40) * shade)),
      )
      const g = Math.max(
        0,
        Math.min(255, Math.round((baseG + grit * 22 + pebbleMask * 25) * shade)),
      )
      const b = Math.max(
        0,
        Math.min(255, Math.round((baseB + grit * 12 + pebbleMask * 18) * shade)),
      )
      const ai = (y * size + x) * 4
      albedo[ai] = r
      albedo[ai + 1] = g
      albedo[ai + 2] = b
      albedo[ai + 3] = 255

      const roughV = 0.75 + grit * 0.2 + pebbleMask * 0.1
      const rv = Math.max(0, Math.min(255, Math.round(roughV * 255)))
      rough[ai] = rv
      rough[ai + 1] = rv
      rough[ai + 2] = rv
      rough[ai + 3] = 255
    }
  }

  const normal = heightToNormal(heights, size, 6.5)
  const map = new CanvasTexture(canvasFromRgba(size, albedo))
  const normalMap = new CanvasTexture(canvasFromRgba(size, normal))
  const roughnessMap = new CanvasTexture(canvasFromRgba(size, rough))
  configureMap(map, true, CHAMBER_MATERIAL.potSoilUvRepeat)
  configureMap(normalMap, false, CHAMBER_MATERIAL.potSoilUvRepeat)
  configureMap(roughnessMap, false, CHAMBER_MATERIAL.potSoilUvRepeat)
  return { map, normalMap, roughnessMap }
}

/**
 * Build felt + soil CanvasTextures (browser only). Call under Canvas / Suspense.
 */
export function createPotPbrMaps(size: number = 256): PotPbrMaps {
  return {
    felt: buildFeltMaps(size),
    soil: buildSoilMaps(size),
  }
}

/** Stable maps for the session (regenerate only if size changes). */
export function usePotPbrMaps(size: number = 256): PotPbrMaps {
  return useMemo(() => createPotPbrMaps(size), [size])
}
