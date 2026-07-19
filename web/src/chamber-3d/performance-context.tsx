/**
 * React context for performance-tier configuration.
 *
 * Wrap scene components; provides tier-aware knobs for geometry segments,
 * shadow resolution, light count, etc. without drilling props.
 *
 * NOTE: FPS is deliberately NOT in this context. Measuring FPS requires
 * frequent state updates that would trigger full canvas re-renders and
 * cause camera stutter. The PerformanceOverlay reads FPS via its own
 * local hook that never propagates to the scene tree.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import {
  getDetectedTier,
  resolveTierConfig,
  setManualTier,
  type PerformanceConfig,
  type PerformanceTier,
} from "@/chamber-3d/performance-tier"

export type ChamberPerformanceCtx = {
  tier: PerformanceTier
  config: PerformanceConfig
  setTier: (tier: PerformanceTier) => void
}

const DEFAULT_CONFIG = resolveTierConfig("medium")

const ChamberPerfCtx = createContext<ChamberPerformanceCtx>({
  tier: "medium",
  config: DEFAULT_CONFIG,
  setTier: () => {},
})

export function useChamberPerformance(): ChamberPerformanceCtx {
  return useContext(ChamberPerfCtx)
}

export function ChamberPerformanceProvider({
  children,
  forcedTier,
  configOverrides,
}: {
  children: ReactNode
  forcedTier?: PerformanceTier
  configOverrides?: Partial<PerformanceConfig>
}) {
  const [tier, setTierState] = useState<PerformanceTier>(
    forcedTier ?? getDetectedTier,
  )

  const setTier = useCallback((t: PerformanceTier) => {
    setManualTier(t)
    setTierState(t)
  }, [])

  const config = useMemo(
    () => resolveTierConfig(tier, configOverrides),
    [tier, configOverrides],
  )

  const value = useMemo<ChamberPerformanceCtx>(
    () => ({ tier, config, setTier }),
    [tier, config, setTier],
  )

  return (
    <ChamberPerfCtx.Provider value={value}>{children}</ChamberPerfCtx.Provider>
  )
}
