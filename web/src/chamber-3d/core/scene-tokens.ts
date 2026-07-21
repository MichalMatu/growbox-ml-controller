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
  /** Stitched top rim bead. */
  potRim: "--chamber-pot-rim",
  /**
   * Soil material tint (white — absolute black potting mix lives in pot-pbr map).
   */
  potSoil: "--chamber-pot-soil",
  /** Grow-light housing / reflector metal. */
  lightHousing: "--chamber-light-housing",
  /** LED board emitter plate. */
  lightEmitter: "--chamber-light-emitter",
  /** Cooltube glass-metal duct tint. */
  lightDuct: "--chamber-light-duct",
  /** HPS bulb glass. */
  lightBulb: "--chamber-light-bulb",
  /** Desaturated scene light tints (point/spot; not mesh emissive). */
  lightLedScene: "--chamber-light-led-scene",
  lightHpsScene: "--chamber-light-hps-scene",
  /** Room context — matte painted drywall / plaster walls and floor. */
  roomWall: "--chamber-room-wall",
  roomFloor: "--chamber-room-floor",
  roomBaseboard: "--chamber-room-baseboard",
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
  /**
   * Interior foil tint (multiplies Foil003 albedo).
   * Near-neutral silver — avoid warm/cream so colored grow lights do not
   * milk the mylar into a pastel haze.
   */
  interior: "#f2f4f7",
  /** Powder-coated steel poles */
  frame: "#141414",
  /** Black plastic zipper coil — reads on silver foil from inside */
  zipper: "#121214",
  /** Charcoal nonwoven felt (real grow bags are near-black matte) */
  potFelt: "#141416",
  potRim: "#0e0e10",
  /** White tint — absolute black soil color is baked into pot-pbr albedo. */
  potSoil: "#ffffff",
  lightHousing: "#1c1c1f",
  /** Mesh emitter / bulb albedo + emissive (can stay slightly tinted). */
  lightEmitter: "#f2f0e6",
  lightDuct: "#9aa3ad",
  lightBulb: "#ffd89a",
  /**
   * Scene light colors (point/spot only). Desaturated vs mesh emissive so
   * specular mylar keeps silver mirror sheen instead of lamp-colored milk.
   */
  lightLedScene: "#f5f6f4",
  lightHpsScene: "#ffe9c8",
  /** Room drywall — warm off-white plaster in light theme. */
  roomWall: "#e8e4dc",
  /** Room floor — light wood / tile tint. */
  roomFloor: "#c4b5a5",
  /** Room baseboard — slightly lighter than wall for subtle separation. */
  roomBaseboard: "#d0ccc6",
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
   * Foil003 mylar — very low roughness + high metal/env so walls read as
   * mirror liner, not matte painted silver. Normal kept moderate (wrinkle).
   * Photorealistic pass: even lower roughness for sharper reflections,
   * higher env map intensity for mirror-like foil.
   */
  interiorRoughness: 0.12,
  interiorMetalness: 0.98,
  interiorNormalScale: 0.22,
  interiorAoIntensity: 0.12,
  interiorEnvMapIntensity: 2.4,

  /** Black powder-coated steel frame — fully dielectric, no env reflections → stays black. */
  frameRoughness: 0.85,
  frameMetalness: 0.0,
  frameEnvMapIntensity: 0.0,
  /** Black plastic zipper — fully matte dielectric */
  zipperRoughness: 0.8,
  zipperMetalness: 0.0,
  zipperEnvMapIntensity: 0.0,
  /**
   * Nonwoven felt grow bag — fully matte dielectric (fabric PBR defaults).
   * High roughness + near-zero env so it never looks plastic/shiny.
   */
  potFeltRoughness: 1,
  potFeltMetalness: 0,
  potFeltEnvMapIntensity: 0.04,
  potFeltNormalScale: 0.65,
  potFeltUvRepeat: 3.2,
  /** Injection-moulded PP plastic pot (smooth, slight gloss for realism). */
  plasticRoughness: 0.42,
  plasticMetalness: 0.06,
  plasticEnvMapIntensity: 0.35,
  plasticUvRepeat: 2.0,
  /**
   * Black potting mix (absolute albedo map).
   * envMapIntensity 0 + toneMapped false on mesh — stops cool HDR/ACES gray wash.
   * roughness ~1 matches common Three.js dirt materials.
   */
  potSoilRoughness: 1,
  potSoilMetalness: 0,
  potSoilEnvMapIntensity: 0,
  potSoilNormalScale: 1.0,
  potSoilUvRepeat: 1.8,
  /** Powder-coated light housings / wings / box hoods */
  lightHousingRoughness: 0.55,
  lightHousingMetalness: 0.65,
  lightHousingEnvMapIntensity: 0.45,
  lightDuctRoughness: 0.28,
  lightDuctMetalness: 0.75,
  /** Emitter glow is visual only (not scene light); keep below fixture intensity. */
  lightEmitterEmissiveOn: 4.5,
  lightEmitterEmissiveOff: 0.04,
  lightBulbEmissiveOn: 6.0,
  lightBulbEmissiveOff: 0.06,
  /**
   * Scene lights on fixtures (only when lit).
   * Base intensities are for reference wattage (LED 200 W / HPS 600 W), then
   * scaled by sqrt(powerW / ref) so 1000 W reads stronger than 600 W without
   * blowing the foil. Form efficiency: box > wing > cooltube; LED is soft/wide.
   */
  ledDiodePitchM: 0.028,
  ledDiodeMaxAxis: 64,
  ledDiodeRadiusScale: 0.32,
  ledPowerRefW: 200,
  hpsPowerRefW: 600,
  /**
   * LED: most energy in a broad spot (less milky multi-point wash on mylar).
   * Fill is a low residual under the board only.
   */
  ledPanelFillIntensity: 20,
  ledPanelSpotIntensity: 140,
  /**
   * HPS: hard warm key from bulb + spot; fill stays small so tent walls do not
   * pick up orange milk — power hierarchy lives in spot/point, not fill.
   */
  hpsPointIntensity: 60,
  hpsSpotIntensity: 120,
  hpsFillIntensity: 10,
  /** Form efficiency vs open box hood (character, not fake watts). */
  hpsFormScaleBox: 1.0,
  hpsFormScaleWing: 0.85,
  hpsFormScaleCooltube: 0.65,
  lightOffSceneIntensity: 0,
  /**
   * Room studio (always on, same whether grow fixture is ON or OFF).
   * Lights sit outside the tent; grow point/spot only add interior key when lit.
   * Do not scale these down when grow-lit — that made the exterior pad go dark
   * (stage layer receives only studio, never grow lamps).
   *
   * Photorealistic pass: softer ambient, stronger key with better fill balance,
   * higher environment intensity for mirror-like foil reflections.
   */
  studioAmbientIntensity: 0.55,
  studioHemisphereIntensity: 0.45,
  studioKeyIntensity: 2.2,
  studioFrontIntensity: 1.6,
  studioTopIntensity: 1.0,
  studioRimLeftIntensity: 0.8,
  studioRimRightIntensity: 0.6,
  /** Warehouse HDR for the whole stage (constant room brightness). */
  environmentIntensity: 1.6,
  /** ACES exposure — constant; room does not change ISO when the lamp toggles. */
  toneMappingExposure: 1.0,
  /**
   * Floor material — matte concrete / epoxy studio floor.
   * Low metalness + high roughness for natural, non-shiny surface.
   */
  floorRoughness: 0.75,
  floorMetalness: 0.02,
  floorEnvMapIntensity: 0.15,
  /** Room drywall — matte painted plaster, near-zero metalness. */
  roomWallRoughness: 0.88,
  roomWallMetalness: 0,
  /** Room floor — slightly smoother than wall, subtle wood/tile sheen. */
  roomFloorRoughness: 0.65,
  roomFloorMetalness: 0.03,
  /** Baseboard — painted wood/MDF, satin finish. */
  roomBaseboardRoughness: 0.55,
  roomBaseboardMetalness: 0.05,
} as const

/**
 * Parametric shell / frame sizes in scene meters.
 * Walls sit on the outer envelope. Frame: tube center = radius + eps from
 * every outer face (same inset on X/Y/Z → orthogonal 90° cage).
 */
export const CHAMBER_GEOMETRY = {
  /** Fabric panel thickness (meters). 2mm matches real grow tent fabric. */
  wallThicknessM: 0.002,
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
  /**
   * Drop of soil surface below the rim lip (fraction of height).
   * Keep large enough that the bag mouth reads open (not a flush lid).
   */
  potSoilInsetScale: 0.16,
  potWallSegments: 28,
} as const

/** DOM class on the R3F Canvas element (fill parent AppCanvasFrame viewport). */
export const CHAMBER_CANVAS_CLASS = "h-full w-full touch-none"

/**
 * Three.js render / light layers for the chamber playground.
 * Grow fixture lights stay on `content` only so they cannot paint a circular
 * spill on the exterior stage floor (Three.js lights ignore mesh occlusion).
 * Studio lights hit both layers; the camera sees both.
 */
export const CHAMBER_LAYER = {
  /** Tent shell, pots, fixtures + grow point/spot lights. */
  content: 0,
  /** Exterior floor + grid only (studio fill, never grow lamps). */
  stage: 1,
} as const

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
    lightLedScene: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightLedScene,
      CHAMBER_SCENE_FALLBACK.lightLedScene,
    ),
    lightHpsScene: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.lightHpsScene,
      CHAMBER_SCENE_FALLBACK.lightHpsScene,
    ),
    roomWall: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.roomWall,
      CHAMBER_SCENE_FALLBACK.roomWall,
    ),
    roomFloor: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.roomFloor,
      CHAMBER_SCENE_FALLBACK.roomFloor,
    ),
    roomBaseboard: readCssVar(
      rootStyle,
      CHAMBER_CSS_VAR.roomBaseboard,
      CHAMBER_SCENE_FALLBACK.roomBaseboard,
    ),
  }
}
