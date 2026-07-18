/**
 * R3F visual tokens. CSS custom properties in `index.css` are the SSOT for colors.
 * This module:
 * - names the CSS variables
 * - provides matching fallbacks (for tests / no-document)
 * - resolves live values via getComputedStyle for Three.js materials
 *
 * Hex literals are allowed ONLY here (fallbacks) and in `index.css`.
 */

/** CSS custom property names — must exist on :root in index.css. */
export const CHAMBER_CSS_VAR = {
  background: "--chamber-bg",
  fog: "--chamber-fog",
  floor: "--chamber-floor",
  gridCell: "--chamber-grid-cell",
  gridSection: "--chamber-grid-section",
  enclosureFill: "--chamber-enclosure-fill",
  enclosureEdge: "--chamber-enclosure-edge",
} as const

/**
 * Fallbacks when `document` is unavailable.
 * Values MUST match the corresponding --chamber-* declarations in index.css.
 */
export const CHAMBER_SCENE_FALLBACK = {
  background: "#0b1220",
  fog: "#0b1220",
  floor: "#111827",
  gridCell: "#1f2937",
  gridSection: "#374151",
  enclosureFill: "#4ade80",
  enclosureEdge: "#22c55e",
} as const

export type ChamberSceneColors = {
  readonly [K in keyof typeof CHAMBER_SCENE_FALLBACK]: string
}

/** Non-color material knobs (not CSS colors; still centralized). */
export const CHAMBER_MATERIAL = {
  enclosureOpacity: 0.18,
} as const

/** DOM class on the R3F Canvas element (fill parent AppCanvasFrame viewport). */
export const CHAMBER_CANVAS_CLASS = "h-full w-full touch-none"

function readCssVar(
  style: CSSStyleDeclaration,
  property: string,
  fallback: string,
): string {
  const value = style.getPropertyValue(property).trim()
  return value.length > 0 ? value : fallback
}

/**
 * Resolve chamber colors from the live document theme.
 * Call from React components (browser only); falls back offline.
 */
export function resolveChamberSceneColors(
  rootStyle: CSSStyleDeclaration | null =
    typeof document !== "undefined"
      ? getComputedStyle(document.documentElement)
      : null,
): ChamberSceneColors {
  if (!rootStyle) {
    return { ...CHAMBER_SCENE_FALLBACK }
  }

  return {
    background: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.background,
      CHAMBER_SCENE_FALLBACK.background,
    ),
    fog: readCssVar(rootStyle, CHAMBER_CSS_VAR.fog, CHAMBER_SCENE_FALLBACK.fog),
    floor: readCssVar(rootStyle, CHAMBER_CSS_VAR.floor, CHAMBER_SCENE_FALLBACK.floor),
    gridCell: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.gridCell,
      CHAMBER_SCENE_FALLBACK.gridCell,
    ),
    gridSection: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.gridSection,
      CHAMBER_SCENE_FALLBACK.gridSection,
    ),
    enclosureFill: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.enclosureFill,
      CHAMBER_SCENE_FALLBACK.enclosureFill,
    ),
    enclosureEdge: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.enclosureEdge,
      CHAMBER_SCENE_FALLBACK.enclosureEdge,
    ),
  }
}

/** @deprecated Use resolveChamberSceneColors() — kept as fallback alias for static imports. */
export const CHAMBER_SCENE = CHAMBER_SCENE_FALLBACK
