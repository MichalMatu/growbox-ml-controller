/**
 * Procedural PBR maps for felt grow bags + soil (no external assets).
 *
 * Felt: grayscale albedo × material.color (charcoal).
 * Soil: absolute-color dirt map × white material (proven Three.js canvas-dirt
 * pattern). toneMapped is disabled on the soil material so ACES + cool
 * studio fill cannot wash black-brown into gray sand.
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
  const pixels = new Uint8ClampedArray(data.length)
  pixels.set(data)
  ctx.putImageData(new ImageData(pixels, size, size), 0, 0)
  return canvas
}

/**
 * Nonwoven felt / fabric grow-bag surface (procedural).
 *
 * Real needle-punched grow bags: matte charcoal, random fibers (not a loom weave),
 * soft low-frequency undulation, very high roughness, almost no env response.
 * Material.color (potFelt) multiplies this grayscale albedo — same pattern as
 * common Three.js fabric materials (map detail × solid cloth tint).
 */
function buildFeltMaps(size: number): PotSurfaceMaps {
  const heights = new Float32Array(size * size)
  const albedo = new Uint8ClampedArray(size * size * 4)
  const rough = new Uint8ClampedArray(size * size * 4)

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size
      const v = y / size

      // Needle-punched felt: multi-direction fine fibers (not a regular weave grid)
      const fiberA = fbm(u * 72 + 0.3, v * 28 - 1.1, 4)
      const fiberB = fbm(u * 30 - 2.0, v * 68 + 0.7, 4)
      const fiberC = fbm(u * 90, v * 90, 3)
      const fibers = fiberA * 0.4 + fiberB * 0.4 + fiberC * 0.2

      // Soft bag undulation (large, gentle)
      const undulation = fbm(u * 4.5 + 1.2, v * 4.5 - 0.8, 3)

      // Sparse darker needle denser spots / lint
      const fleck = hash2(x * 0.41, y * 0.87)
      const dense = fleck > 0.93 ? (fleck - 0.93) / 0.07 : 0
      // Tiny bright lint picks (very subtle on black felt)
      const lint = fleck < 0.04 ? (0.04 - fleck) / 0.04 : 0

      const h =
        fibers * 0.55 +
        undulation * 0.28 +
        dense * 0.2 +
        lint * 0.12 +
        hash2(x, y) * 0.05
      heights[y * size + x] = h

      // Grayscale multiplier for charcoal potFelt color.
      // Keep mid-high so bag stays near-black, not mid-gray plastic.
      const lum =
        0.72 +
        fibers * 0.14 +
        undulation * 0.08 -
        dense * 0.22 +
        lint * 0.1
      const c = Math.max(0, Math.min(255, Math.round(lum * 255)))
      const ai = (y * size + x) * 4
      albedo[ai] = c
      albedo[ai + 1] = c
      albedo[ai + 2] = c
      albedo[ai + 3] = 255

      // Felt is almost fully rough — only tiny variance
      const r = 0.96 + fibers * 0.03 - dense * 0.02 + lint * 0.01
      const rv = Math.max(0, Math.min(255, Math.round(r * 255)))
      rough[ai] = rv
      rough[ai + 1] = rv
      rough[ai + 2] = rv
      rough[ai + 3] = 255
    }
  }

  // Mild normals — strong relief reads as rubber, not soft felt
  const normal = heightToNormal(heights, size, 2.8)
  const map = new CanvasTexture(canvasFromRgba(size, albedo))
  const normalMap = new CanvasTexture(canvasFromRgba(size, normal))
  const roughnessMap = new CanvasTexture(canvasFromRgba(size, rough))
  configureMap(map, true, CHAMBER_MATERIAL.potFeltUvRepeat)
  configureMap(normalMap, false, CHAMBER_MATERIAL.potFeltUvRepeat)
  configureMap(roughnessMap, false, CHAMBER_MATERIAL.potFeltUvRepeat)
  return { map, normalMap, roughnessMap }
}

/**
 * Horticultural perlite flecks — sparse scatter matching real potting-mix photos.
 */
function perliteCoverage(x: number, y: number, size: number): number {
  let coverage = 0
  coverage = Math.max(coverage, grainField(x, y, size, 12, 0.88, 0.8, 2.4))
  coverage = Math.max(coverage, grainField(x, y, size, 18, 0.92, 1.3, 3.4))
  coverage = Math.max(coverage, grainField(x, y, size, 5.5, 0.94, 0.4, 1.1))
  return Math.min(1, coverage)
}

/** One scale of random soft discs in a sparse cell grid. */
function grainField(
  x: number,
  y: number,
  size: number,
  cellPx: number,
  densityThreshold: number,
  minRadiusPx: number,
  maxRadiusPx: number,
): number {
  const scale = size / 256
  const cell = Math.max(2, Math.round(cellPx * scale))
  const cx = Math.floor(x / cell)
  const cy = Math.floor(y / cell)
  let best = 0
  for (let oy = -1; oy <= 1; oy++) {
    for (let ox = -1; ox <= 1; ox++) {
      const ix = cx + ox
      const iy = cy + oy
      const spawn = hash2(ix * 19.7 + 2.3, iy * 23.1 - 1.1)
      if (spawn < densityThreshold) continue
      const jx = hash2(ix * 41.3, iy * 17.9)
      const jy = hash2(ix * 7.1 + 0.4, iy * 13.7)
      const px = (ix + jx) * cell
      const py = (iy + jy) * cell
      const radius =
        (minRadiusPx +
          hash2(ix * 2.2, iy * 3.7) * (maxRadiusPx - minRadiusPx)) *
        scale
      const d = Math.hypot(x - px, y - py)
      if (d >= radius) continue
      const t = 1 - d / radius
      const ragged =
        0.65 + 0.35 * hash2(Math.floor(x * 0.9), Math.floor(y * 0.9))
      const strength = t * t * (0.7 + spawn * 0.3) * ragged
      if (strength > best) best = strength
    }
  }
  return best
}

/**
 * Black potting-mix albedo (absolute RGB in the map).
 *
 * Pattern from common Three.js procedural dirt (CanvasTexture + StandardMaterial):
 * solid base fill + darker flecks; material.color stays white so the map is SSOT.
 * Adapted for black grow-bag soil + white perlite (not Material-brown sand).
 *
 * RGB numbers only here (hex literals forbidden outside scene-tokens / CSS).
 * Base ~ (22,14,10) black-brown; dark pores; sparse off-white perlite.
 */
function buildSoilMaps(size: number): PotSurfaceMaps {
  const heights = new Float32Array(size * size)
  const albedo = new Uint8ClampedArray(size * size * 4)
  const rough = new Uint8ClampedArray(size * size * 4)

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size
      const v = y / size
      const clump = fbm(u * 6, v * 6, 4)
      const mid = fbm(u * 18 + 1.2, v * 18 - 0.7, 3)
      const grit = fbm(u * 50, v * 50, 2)
      const jitter = hash2(x * 1.7, y * 2.3)
      const perlite = perliteCoverage(x, y, size)

      const h =
        clump * 0.5 + mid * 0.28 + grit * 0.14 + perlite * 0.4 + jitter * 0.05
      heights[y * size + x] = h

      // Absolute black potting soil (warm black-brown, not gray/sand).
      // MeshBasicMaterial shows these values as authored — keep them dark.
      let r = 14 + clump * 12 + mid * 5
      let g = 9 + clump * 7 + mid * 3
      let b = 6 + clump * 3 + mid * 1.5

      if (jitter < 0.1) {
        // darker wet pockets
        const wet = (0.1 - jitter) / 0.1
        r *= 1 - wet * 0.5
        g *= 1 - wet * 0.5
        b *= 1 - wet * 0.5
      }

      // White perlite flecks (photo-accurate grow mix)
      if (perlite > 0.06) {
        const p = Math.min(0.9, perlite)
        const pr = 210 + hash2(x + 2, y) * 35
        const pg = 206 + hash2(x, y + 3) * 32
        const pb = 198 + hash2(x + 1, y + 1) * 28
        r = r * (1 - p) + pr * p
        g = g * (1 - p) + pg * p
        b = b * (1 - p) + pb * p
      }

      const ai = (y * size + x) * 4
      albedo[ai] = Math.max(0, Math.min(255, Math.round(r)))
      albedo[ai + 1] = Math.max(0, Math.min(255, Math.round(g)))
      albedo[ai + 2] = Math.max(0, Math.min(255, Math.round(b)))
      albedo[ai + 3] = 255

      // Matte soil (gist dirt uses ~0.8; we stay fully rough)
      const roughV = 0.92 + grit * 0.06 - perlite * 0.05
      const rv = Math.max(0, Math.min(255, Math.round(roughV * 255)))
      rough[ai] = rv
      rough[ai + 1] = rv
      rough[ai + 2] = rv
      rough[ai + 3] = 255
    }
  }

  const normal = heightToNormal(heights, size, 4.0)
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
