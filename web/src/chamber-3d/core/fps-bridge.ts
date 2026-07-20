/**
 * Shared FPS store — written by <FpsReporter> inside the R3F Canvas
 * (via useFrame), read by the DOM overlay via useSyncExternalStore.
 *
 * Returns a number (primitive) to satisfy useSyncExternalStore's
 * referential equality requirement. Ready state is implied by fps > 0.
 */
let fps = 0
const listeners = new Set<() => void>()

export function reportFps(value: number): void {
  fps = Math.round(value)
  for (const fn of listeners) fn()
}

export function getFpsSnapshot(): number {
  return fps
}

export function subscribeToFps(cb: () => void): () => void {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}
