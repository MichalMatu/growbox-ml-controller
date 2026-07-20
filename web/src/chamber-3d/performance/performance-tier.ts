/**
 * Adaptive performance tier for the chamber-3d playground.
 *
 * Tiers progressively reduce geometry segments, shadow map resolution,
 * scene-light count, and texturing quality to keep the frame-rate usable
 * on low-end integrated GPUs and mobile devices.
 *
 * Detection is automatic; manual override via URL param or localStorage
 * always wins.
 */

export type PerformanceTier = "ultra" | "high" | "medium" | "low"

export type PerformanceConfig = {
  /** Canvas DPR ceiling. */
  dprMax: number
  /** Shadow map size (square). */
  shadowMapSize: number
  /** Grow fixture castShadow (point + spot). */
  fixtureShadows: boolean
  /** How many of the 6 static studio lights to enable. */
  studioLightCount: number
  /** Use the warehouse HDR Environment map. */
  environmentMap: boolean
  /** Environment map resolution (cubemap face size). */
  environmentResolution: number
  /** Frame tube radial segments. */
  frameRadialSegments: number
  /** Pot wall / rim / soil radial segments. */
  potWallSegments: number
  /** Tent panel UV tile repeat divisor (1 = full, 2 = half tiles). */
  panelUvDivisor: number
  /** Pot PBR canvas texture size. */
  potPbrSize: number
  /** Grid component (drei) enabled. */
  floorGrid: boolean
  /** Fog enabled. */
  fog: boolean
  /** ACESFilmicToneMapping exposure. */
  toneMappingExposure: number
}

const TIER_LABELS: Record<PerformanceTier, string> = {
  ultra: "Ultra",
  high: "High",
  medium: "Medium",
  low: "Low",
}

/** Manual tier set via `?tier=low` or localStorage `chamber-3d-tier`. */
function readManualTier(): PerformanceTier | null {
  if (typeof window === "undefined") return null
  const url = new URL(window.location.href)
  const param = url.searchParams.get("tier")
  if (param && (param === "ultra" || param === "high" || param === "medium" || param === "low")) {
    return param as PerformanceTier
  }
  try {
    const stored = localStorage.getItem("chamber-3d-tier")
    if (stored && (stored === "ultra" || stored === "high" || stored === "medium" || stored === "low")) {
      return stored as PerformanceTier
    }
  } catch {
    // localStorage unavailable
  }
  return null
}

/**
 * Auto-detect hardware tier from heuristics.
 * Runs once on import (module-level) so it is stable for the session.
 */
function detectTier(): PerformanceTier {
  const manual = readManualTier()
  if (manual) return manual

  if (typeof navigator === "undefined") return "medium"

  const memory = (navigator as unknown as Record<string, unknown>).deviceMemory as number | undefined
  const cores = navigator.hardwareConcurrency ?? 4
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio : 2

  // Heuristic score: lower = weaker device
  let score = 0
  if (memory != null) score += memory >= 8 ? 2 : memory >= 4 ? 1 : 0
  score += cores >= 8 ? 2 : cores >= 4 ? 1 : 0
  score += dpr >= 2 ? 1 : 0

  if (score >= 5) return "ultra"
  if (score >= 3) return "high"
  if (score >= 2) return "medium"
  return "low"
}

const DETECTED_TIER: PerformanceTier = detectTier()

export function getDetectedTier(): PerformanceTier {
  return DETECTED_TIER
}

export function setManualTier(tier: PerformanceTier): void {
  try {
    localStorage.setItem("chamber-3d-tier", tier)
  } catch {
    // ignore
  }
}

export function getTierLabel(tier: PerformanceTier): string {
  return TIER_LABELS[tier]
}

/**
 * FPS bucketing for the overlay (not used for auto-tier switching to avoid
 * ping-pong; manual tier only during a session).
 */
export function classifyFps(fps: number): string {
  if (fps >= 55) return "🟢 " + Math.round(fps)
  if (fps >= 30) return "🟡 " + Math.round(fps)
  return "🔴 " + Math.round(fps)
}

/**
 * Resolve tier configuration.
 * Pass in overrides (e.g. lit=true may want shadows even on low).
 */
export function resolveTierConfig(
  tier: PerformanceTier,
  overrides?: Partial<PerformanceConfig>,
): PerformanceConfig {
  const base: PerformanceConfig = (() => {
    switch (tier) {
      case "ultra":
        return {
          dprMax: 2,
          shadowMapSize: 1024,
          fixtureShadows: true,
          studioLightCount: 6,
          environmentMap: true,
          environmentResolution: 256,
          frameRadialSegments: 12,
          potWallSegments: 28,
          panelUvDivisor: 1,
          potPbrSize: 384,
          floorGrid: true,
          fog: true,
          toneMappingExposure: 1.0,
        }
      case "high":
        return {
          dprMax: 1.5,
          shadowMapSize: 1024,
          fixtureShadows: true,
          studioLightCount: 6,
          environmentMap: true,
          environmentResolution: 128,
          frameRadialSegments: 10,
          potWallSegments: 22,
          panelUvDivisor: 1,
          potPbrSize: 256,
          floorGrid: true,
          fog: true,
          toneMappingExposure: 1.0,
        }
      case "medium":
        return {
          dprMax: 1,
          shadowMapSize: 512,
          fixtureShadows: true,
          studioLightCount: 4,
          environmentMap: true,
          environmentResolution: 64,
          frameRadialSegments: 8,
          potWallSegments: 16,
          panelUvDivisor: 2,
          potPbrSize: 128,
          floorGrid: false,
          fog: false,
          toneMappingExposure: 0.95,
        }
      case "low":
        return {
          dprMax: 0.75,
          shadowMapSize: 256,
          fixtureShadows: false,
          studioLightCount: 4,
          environmentMap: true,
          environmentResolution: 32,
          frameRadialSegments: 6,
          potWallSegments: 10,
          panelUvDivisor: 4,
          potPbrSize: 64,
          floorGrid: false,
          fog: false,
          toneMappingExposure: 1.0,
        }
    }
  })()

  return overrides ? { ...base, ...overrides } : base
}
