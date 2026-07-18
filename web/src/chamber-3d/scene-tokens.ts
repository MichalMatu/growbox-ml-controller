/**
 * R3F / canvas visual tokens — only place for 3D hex colors and canvas DOM class.
 * Feature pages must not pass freehand className into the scene.
 */

/** DOM class on the R3F Canvas element (fill parent frame from AppCanvasFrame). */
export const CHAMBER_CANVAS_CLASS = "h-full w-full touch-none"

export const CHAMBER_SCENE = {
  background: "#0b1220",
  fog: "#0b1220",
  floor: "#111827",
  gridCell: "#1f2937",
  gridSection: "#374151",
  enclosureFill: "#4ade80",
  enclosureEdge: "#22c55e",
} as const
