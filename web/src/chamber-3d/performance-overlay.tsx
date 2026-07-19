import { useCallback, useSyncExternalStore } from "react"

import {
  getFpsSnapshot,
  subscribeToFps,
} from "@/chamber-3d/fps-bridge"
import { useChamberPerformance } from "@/chamber-3d/performance-context"
import {
  classifyFps,
  getTierLabel,
  type PerformanceTier,
} from "@/chamber-3d/performance-tier"

const TIERS: PerformanceTier[] = ["ultra", "high", "medium", "low"]

function isDebugMode(): boolean {
  if (typeof window === "undefined") return false
  try {
    const url = new URL(window.location.href)
    return url.searchParams.has("debug")
  } catch {
    return false
  }
}

export function PerformanceOverlay() {
  const { tier, setTier, config } = useChamberPerformance()

  // Read real WebGL FPS from the shared bridge (written by FpsReporter inside Canvas)
  const rawFps = useSyncExternalStore(subscribeToFps, getFpsSnapshot)

  const handleTierChange = useCallback(
    (next: PerformanceTier) => {
      setTier(next)
    },
    [setTier],
  )

  if (!isDebugMode()) return null

  const fpsDisplay = rawFps > 0 ? classifyFps(rawFps) : "…"

  return (
    <div
      style={{
        position: "absolute",
        top: 8,
        left: 8,
        zIndex: 200,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: 11,
        lineHeight: "18px",
        color: "#e4e4e7",
        userSelect: "none",
        pointerEvents: "none",
        textShadow: "0 1px 3px rgba(0,0,0,0.8)",
      }}
    >
      <div style={{ pointerEvents: "none" }}>
        <span style={{ opacity: 0.55 }}>FPS</span> {fpsDisplay}
      </div>
      <div style={{ pointerEvents: "none" }}>
        <span style={{ opacity: 0.55 }}>Tier</span>{" "}
        {TIERS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => handleTierChange(t)}
            style={{
              background: "none",
              border: t === tier ? "1px solid rgba(255,255,255,0.4)" : "1px solid transparent",
              borderRadius: 3,
              color: t === tier ? "#fff" : "rgba(255,255,255,0.45)",
              padding: "0 4px",
              marginLeft: 2,
              cursor: "pointer",
              fontSize: 11,
              fontFamily: "inherit",
              lineHeight: "16px",
              pointerEvents: "auto",
            }}
          >
            {getTierLabel(t)}
          </button>
        ))}
      </div>
      <div style={{ opacity: 0.4, pointerEvents: "none" }}>
        dpr={config.dprMax} sh={config.shadowMapSize} env={config.environmentResolution}{" "}
        L={config.studioLightCount} seg={config.potWallSegments}
      </div>
    </div>
  )
}
