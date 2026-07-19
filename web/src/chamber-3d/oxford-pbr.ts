/**
 * Procedural oxford fabric PBR maps — 600D twill weave (grow tent exterior).
 *
 * Real grow tents (Mars Hydro / Costway style) use thick oxford fabric,
 * not smooth nylon. Key visual traits:
 * - Diagonal twill pattern (2-over-1-under weave structure)
 * - Matte charcoal-graphite color (~#1a1a20)
 * - Deep weave grooves (strong normal map, scale 0.65–0.9)
 * - Slight roughness variation between threads and valleys
 *
 * Generated at 512×512 as CanvasTextures, cached via useMemo.
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

export type OxfordPbrMaps = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
  aoMap: Texture
}

/** Twill weave parameters — 2-over-1 pattern creates the diagonal ridge. */
const THREAD_WIDTH_PX = 8
const THREAD_GAP_PX = 2

function hash2(x: number, y: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123
  return s - Math.floor(s)
}

/** Smooth value noise per pixel — thread micro-variation. */
function noise(px: number, py: number): number {
  const fx = px - Math.floor(px)
  const fy = py - Math.floor(py)
  const ux = fx * fx * (3 - 2 * fx)
  const uy = fy * fy * (3 - 2 * fy)
  const a = hash2(Math.floor(px), Math.floor(py))
  const b = hash2(Math.floor(px) + 1, Math.floor(py))
  const c = hash2(Math.floor(px), Math.floor(py) + 1)
  const d = hash2(Math.floor(px) + 1, Math.floor(py) + 1)
  return a * (1 - ux) * (1 - uy) + b * ux * (1 - uy) + c * (1 - ux) * uy + d * ux * uy
}

function configureOxfordTexture(texture: Texture, isColor: boolean, repeat: number): void {
  texture.colorSpace = isColor ? SRGBColorSpace : NoColorSpace
  texture.wrapS = RepeatWrapping
  texture.wrapT = RepeatWrapping
  texture.repeat.set(repeat, repeat)
  texture.magFilter = LinearFilter
  texture.minFilter = LinearMipmapLinearFilter
  texture.anisotropy = 8
  texture.generateMipmaps = true
  texture.needsUpdate = true
}

function heightToNormalRGBA(
  heights: Float32Array,
  size: number,
  strength: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
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
      const o = (y * size + x) * 4
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
  if (!ctx) throw new Error("2d canvas unavailable")
  const pixels = new Uint8ClampedArray(data.length)
  pixels.set(data)
  ctx.putImageData(new ImageData(pixels, size, size), 0, 0)
  return canvas
}

/**
 * Generate oxford twill weave textures at given size.
 */
function buildOxfordMaps(size: number): {
  map: CanvasTexture
  normalMap: CanvasTexture
  roughnessMap: CanvasTexture
  aoMap: CanvasTexture
} {
  const heights = new Float32Array(size * size)
  const albedo = new Uint8ClampedArray(size * size * 4)
  const rough = new Uint8ClampedArray(size * size * 4)
  const ao = new Uint8ClampedArray(size * size * 4)

  // Thread parameters in pixels at this texture size
  const scale = size / 512
  const tw = Math.max(2, Math.round(THREAD_WIDTH_PX * scale))
  const gap = Math.max(1, Math.round(THREAD_GAP_PX * scale))
  const period = tw * 3

  // Diagonal angle (roughly 45° for classic twill)
  const angle = Math.PI / 4

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // Rotate coordinates to match diagonal twill direction
      const rx = x * Math.cos(angle) - y * Math.sin(angle)
      const ry = x * Math.sin(angle) + y * Math.cos(angle)

      // Phase offset for 2/1 twill: each row shifts by 1 thread width
      const rowShift = (Math.floor(ry / tw) % 3) * tw
      const px = (rx + rowShift + period) % period

      // Determine if pixel is on a raised thread or in a valley
      const threadPhase = px % (tw + gap)
      const isThread = threadPhase < tw

      // 2/1 twill pattern: two consecutive rows raised, one lowered
      const weaveRow = Math.floor(ry / tw) % 3
      const isRaised = weaveRow < 2 ? isThread : !isThread

      // Micro-variation from thread fibers
      const fiberNoise = noise(x * 0.4, y * 0.4) * 0.15

      // Height: raised thread ~0.7, valley ~0.0
      let h: number
      if (isRaised) {
        h = 0.72 + fiberNoise * 0.28
        // Edge transition: slight rounding at thread boundaries
        const edge = threadPhase / tw
        if (edge < 0.15) h *= 0.55 + edge * 3.0
        else if (edge > 0.85) h *= 0.55 + (1 - edge) * 3.0
      } else {
        h = 0.08 + fiberNoise * 0.12
      }

      heights[y * size + x] = h

      // Albedo: charcoal-graphite base with subtle thread variation
      const baseR = 28
      const baseG = 30
      const baseB = 34

      const threadVar = noise(x * 0.3, y * 0.3) * 5
      const valleyDark = isRaised ? 0 : -4

      const ai = (y * size + x) * 4
      albedo[ai] = Math.max(0, Math.min(255, baseR + threadVar + valleyDark + Math.round(noise(x * 1.5, y * 1.5) * 4)))
      albedo[ai + 1] = Math.max(0, Math.min(255, baseG + threadVar + valleyDark + Math.round(noise(x * 1.5 + 1, y * 1.5 + 1) * 4)))
      albedo[ai + 2] = Math.max(0, Math.min(255, baseB + threadVar + valleyDark + Math.round(noise(x * 1.5 + 2, y * 1.5 + 2) * 4)))
      albedo[ai + 3] = 255

      // Roughness: threads slightly smoother from tight weave, valleys rougher
      const baseRough = isRaised ? 0.82 : 0.95
      const rv = baseRough + fiberNoise * 0.1
      const rc = Math.max(0, Math.min(255, Math.round(rv * 255)))
      rough[ai] = rc
      rough[ai + 1] = rc
      rough[ai + 2] = rc
      rough[ai + 3] = 255

      // AO: valleys darker, deep grooves occluded
      const aoVal = isRaised ? 0.92 : 0.55 + fiberNoise * 0.15
      const ac = Math.max(0, Math.min(255, Math.round(aoVal * 255)))
      ao[ai] = ac
      ao[ai + 1] = ac
      ao[ai + 2] = ac
      ao[ai + 3] = 255
    }
  }

  const normal = heightToNormalRGBA(heights, size, 12.0)

  const mapTex = new CanvasTexture(canvasFromRgba(size, albedo))
  const normalTex = new CanvasTexture(canvasFromRgba(size, normal))
  const roughTex = new CanvasTexture(canvasFromRgba(size, rough))
  const aoTex = new CanvasTexture(canvasFromRgba(size, ao))

  // Tiling: ~3 repeats per meter of real fabric (thread pattern visible but not tiled)
  configureOxfordTexture(mapTex, true, 2.5)
  configureOxfordTexture(normalTex, false, 2.5)
  configureOxfordTexture(roughTex, false, 2.5)
  configureOxfordTexture(aoTex, false, 2.5)

  return { map: mapTex, normalMap: normalTex, roughnessMap: roughTex, aoMap: aoTex }
}

/**
 * Build oxford maps once (must be under Canvas / Suspense).
 */
export function createOxfordPbrMaps(size: number = 512): OxfordPbrMaps {
  return buildOxfordMaps(size)
}

/** Stable hook version for React components. */
export function useOxfordPbrMaps(size: number = 512): OxfordPbrMaps {
  return useMemo(() => createOxfordPbrMaps(size), [size])
}
