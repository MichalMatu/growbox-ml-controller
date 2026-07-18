/**
 * R3F visual tokens. CSS custom properties in `index.css` are the SSOT for colors.
 * This module:
 * - names the CSS variables
 * - provides matching fallbacks (for tests / no-document)
 * - resolves live values via getComputedStyle for Three.js materials
 * - centralizes non-color material / geometry knobs
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
  exterior: "--chamber-exterior",
  interior: "--chamber-interior",
  frame: "--chamber-frame",
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
  /** Outer nylon tent fabric tint (multiplies FreePBR albedo) */
  exterior: "#3a3a40",
  /** Soft fill / hemisphere only (foil albedo uses white + PBR maps) */
  interior: "#b8c2ce",
  /** Powder-coated steel poles */
  frame: "#1e1e1e",
} as const

export type ChamberSceneColors = {
  readonly [K in keyof typeof CHAMBER_SCENE_FALLBACK]: string
}

/** Non-color material knobs (not CSS colors; still centralized). */
export const CHAMBER_MATERIAL = {
  /** FreePBR nylon tent — matte fabric (maps drive detail) */
  exteriorRoughness: 0.95,
  exteriorMetalness: 0,
  exteriorNormalScale: 0.85,
  exteriorAoIntensity: 0.85,
  /** ambientCG Foil003 — reflective foil / mylar stand-in */
  interiorRoughness: 0.2,
  interiorMetalness: 0.9,
  interiorNormalScale: 1.15,
  interiorAoIntensity: 0.55,
  frameRoughness: 0.42,
  frameMetalness: 0.55,
} as const

/**
 * Parametric shell / frame sizes in scene meters.
 * Walls sit on the outer envelope; frame poles sit just inside the fabric.
 */
export const CHAMBER_GEOMETRY = {
  /** Fabric panel thickness (meters). */
  wallThicknessM: 0.016,
  /** Steel tube outer radius (meters) ~ 3.6 cm diameter — readable on foil */
  frameRadiusM: 0.018,
  /** Radial segments for frame cylinders. */
  frameRadialSegments: 12,
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
    exterior: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.exterior,
      CHAMBER_SCENE_FALLBACK.exterior,
    ),
    interior: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.interior,
      CHAMBER_SCENE_FALLBACK.interior,
    ),
    frame: readCssVar(rootStyle, CHAMBER_CSS_VAR.frame, CHAMBER_SCENE_FALLBACK.frame),
  }
}

/** @deprecated Use resolveChamberSceneColors() — kept as fallback alias for static imports. */
export const CHAMBER_SCENE = CHAMBER_SCENE_FALLBACK
