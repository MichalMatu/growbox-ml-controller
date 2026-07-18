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
  /** Plastic zipper track on the rear mesh flap (must read on black nylon). */
  zipper: "--chamber-zipper",
  /** Nonwoven felt grow bag body. */
  potFelt: "--chamber-pot-felt",
  /** Stitched top rim / handles. */
  potRim: "--chamber-pot-rim",
  /** Exposed soil disc inside the bag. */
  potSoil: "--chamber-pot-soil",
  /** Grow-light housing / reflector metal. */
  lightHousing: "--chamber-light-housing",
  /** LED board emitter plate. */
  lightEmitter: "--chamber-light-emitter",
  /** Cooltube glass-metal duct tint. */
  lightDuct: "--chamber-light-duct",
  /** HPS bulb glass. */
  lightBulb: "--chamber-light-bulb",
} as const

/**
 * Fallbacks when `document` is unavailable.
 * Stage bg/fog match `.dark` navy (app default). Light uses softer grays in :root CSS;
 * visible stage fill is CSS --chamber-bg-gradient (canvas is transparent).
 * Other keys match shared --chamber-* declarations in index.css.
 */
export const CHAMBER_SCENE_FALLBACK = {
  background: "#0b1220",
  fog: "#0b1220",
  floor: "#111827",
  gridCell: "#1f2937",
  gridSection: "#374151",
  /**
   * Outer nylon tint (multiplies FreePBR albedo).
   * Real grow tents: near-black matte canvas (Costway / Mars Hydro style).
   */
  exterior: "#0c0c0e",
  /** Soft fill / hemisphere (foil mesh uses cool silver tint + maps) */
  interior: "#e8eef4",
  /** Powder-coated steel poles */
  frame: "#141414",
  /** Black plastic zipper coil — reads on silver foil from inside */
  zipper: "#121214",
  /** Charcoal nonwoven felt (real grow bags are near-black) */
  potFelt: "#1a1a1c",
  potRim: "#121214",
  potSoil: "#3b2a1f",
  lightHousing: "#1c1c1f",
  lightEmitter: "#f2f0e6",
  lightDuct: "#9aa3ad",
  lightBulb: "#ffd89a",
} as const

export type ChamberSceneColors = {
  readonly [K in keyof typeof CHAMBER_SCENE_FALLBACK]: string
}

/** Non-color material knobs (not CSS colors; still centralized). */
export const CHAMBER_MATERIAL = {
  /** FreePBR nylon — matte, low normal so weave is subtle, not shiny */
  exteriorRoughness: 0.98,
  exteriorMetalness: 0,
  exteriorNormalScale: 0.22,
  exteriorAoIntensity: 0.45,
  exteriorEnvMapIntensity: 0.05,
  /**
   * Foil003 is wrinkled — moderate normal relief (more than flat, less than
   * crumpled foil bag) + metalness/env high for bright silver mylar.
   */
  interiorRoughness: 0.3,
  interiorMetalness: 0.9,
  interiorNormalScale: 0.32,
  interiorAoIntensity: 0.22,
  interiorEnvMapIntensity: 1.45,
  frameRoughness: 0.48,
  frameMetalness: 0.5,
  frameEnvMapIntensity: 0.6,
  /** Black plastic zipper — slight sheen so coil edges catch light indoors */
  zipperRoughness: 0.42,
  zipperMetalness: 0.55,
  zipperEnvMapIntensity: 0.7,
  /** Nonwoven felt — very matte, no metal; maps from pot-pbr.ts */
  potFeltRoughness: 0.92,
  potFeltMetalness: 0,
  potFeltEnvMapIntensity: 0.12,
  potFeltNormalScale: 1.15,
  potFeltUvRepeat: 2.4,
  potSoilRoughness: 0.9,
  potSoilMetalness: 0,
  potSoilEnvMapIntensity: 0.06,
  potSoilNormalScale: 1.65,
  potSoilUvRepeat: 1.8,
  /** Powder-coated light housings / wings / box hoods */
  lightHousingRoughness: 0.55,
  lightHousingMetalness: 0.65,
  lightHousingEnvMapIntensity: 0.45,
  lightDuctRoughness: 0.28,
  lightDuctMetalness: 0.75,
  lightEmitterEmissiveOn: 2.4,
  lightEmitterEmissiveOff: 0.04,
  lightBulbEmissiveOn: 3.2,
  lightBulbEmissiveOff: 0.06,
  /** Scene lights attached to fixtures (only when lit). */
  ledDiodePitchM: 0.028,
  ledDiodeMaxAxis: 14,
  ledDiodeRadiusScale: 0.32,
  ledPanelFillIntensity: 3.2,
  ledPanelSpotIntensity: 18,
  hpsPointIntensity: 28,
  hpsSpotIntensity: 42,
  hpsFillIntensity: 6,
  lightOffSceneIntensity: 0,
} as const

/**
 * Parametric shell / frame sizes in scene meters.
 * Walls sit on the outer envelope. Frame: tube center = radius + eps from
 * every outer face (same inset on X/Y/Z → orthogonal 90° cage).
 */
export const CHAMBER_GEOMETRY = {
  /** Fabric panel thickness (meters). */
  wallThicknessM: 0.016,
  /** Steel tube outer radius (meters) ~ 3.6 cm diameter — readable on foil */
  frameRadiusM: 0.018,
  /**
   * Sub-mm clearance so tube skin does not z-fight fabric planes.
   * Not a visible design gap (≈0.5 mm).
   */
  frameContactEpsilonM: 0.0005,
  /** Radial segments for frame cylinders. */
  frameRadialSegments: 12,
  /** Texture tiles per scene-meter (foil / nylon density). */
  uvTilesPerMeter: 100 / 58,
  /**
   * Rear mesh-flap rectangular zipper (no cutout) — fixed real-world size.
   * 30 cm wide × 20 cm high, bottom edge 20 cm above the floor.
   * Shown only when tent width is within [min, max] (typical mid-size tents).
   */
  rearFlapWidthM: 0.3,
  rearFlapHeightM: 0.2,
  /** Bottom edge of the zipper rectangle above the floor (meters). */
  rearFlapBottomYFromFloorM: 0.2,
  /** Inclusive tent-width band (meters) that gets a rear window. */
  rearFlapMinTentWidthM: 0.6,
  rearFlapMaxTentWidthM: 1.2,
  /** Push zipper off the interior foil face to avoid z-fight. */
  rearFlapOutlineOffsetM: 0.003,
  /** Zipper coil radius (~5.5 mm) — thick enough to read on foil. */
  rearFlapZipperRadiusM: 0.0055,
  /** Zipper pull tab size (width, height, depth) in meters. */
  rearFlapZipperPullM: [0.022, 0.014, 0.01] as const,
  /**
   * Felt pot mesh proportions (relative to diameter / height).
   * Soft bag: slight top taper, stitched rim overlapping full-height wall,
   * soil radius must match wall radius at soilY (see felt-pot.tsx layout).
   * Layers must not share coplanar faces (rim/body/soil) — causes z-fight shimmer.
   */
  potTopRadiusScale: 0.96,
  potRimHeightScale: 0.06,
  /** Rim outer radius as fraction beyond wall top radius. */
  potRimRadiusExtraScale: 0.025,
  /** Extra drop of soil surface below the rim lip (fraction of height). */
  potSoilInsetScale: 0.08,
  potWallSegments: 28,
  potHandleRadiusScale: 0.018,
  potHandleWidthScale: 0.28,
  potHandleHeightScale: 0.1,
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
    zipper: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.zipper,
      CHAMBER_SCENE_FALLBACK.zipper,
    ),
    potFelt: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.potFelt,
      CHAMBER_SCENE_FALLBACK.potFelt,
    ),
    potRim: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.potRim,
      CHAMBER_SCENE_FALLBACK.potRim,
    ),
    potSoil: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.potSoil,
      CHAMBER_SCENE_FALLBACK.potSoil,
    ),
    lightHousing: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightHousing,
      CHAMBER_SCENE_FALLBACK.lightHousing,
    ),
    lightEmitter: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightEmitter,
      CHAMBER_SCENE_FALLBACK.lightEmitter,
    ),
    lightDuct: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightDuct,
      CHAMBER_SCENE_FALLBACK.lightDuct,
    ),
    lightBulb: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightBulb,
      CHAMBER_SCENE_FALLBACK.lightBulb,
    ),
  }
}
