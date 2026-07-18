/**
 * Explicit allowlist of feature-UI surfaces.
 *
 * Agents / humans building pages may ONLY compose from:
 * 1. Named component exports of `@/components/app-chrome` (see ALLOWED_APP_CHROME_EXPORTS)
 * 2. shadcn primitives under `@/components/ui/*` — **without** `className` / `style` overrides
 * 3. Domain modules under `@/domain/*` (no styles)
 *
 * Forbidden in feature surfaces:
 * - any `className=…` (string, template, or variable)
 * - any `style=…`
 * - `cn("…")` / freehand Tailwind
 * - one-off Button sizes (only omit size, or `icon` for icon-only)
 *
 * Style owners (may contain Tailwind):
 * - `src/components/app-chrome.tsx`
 * - `src/components/ui/**`
 * - `src/index.css`
 * - `src/chamber-3d/scene-tokens.ts` (R3F materials / canvas DOM class only)
 *
 * Enforced by: eslint.config.js + src/ui-consistency.test.ts (pre-commit web lint/test).
 */

/** Component exports that feature code is allowed to import from app-chrome. */
export const ALLOWED_APP_CHROME_EXPORTS = [
  "AppPage",
  "AppPageHeader",
  "AppPageFooter",
  "AppPageLoading",
  "AppMutedText",
  "AppFieldMetaText",
  "AppSectionTitle",
  "AppSubsectionTitle",
  "AppSection",
  "AppSectionIntro",
  "AppStack",
  "AppActionRow",
  "AppCardBody",
  "AppFormField",
  "AppControlSurface",
  "AppControlLabelBlock",
  "AppFieldStack",
  "AppErrorList",
  "AppHiddenFileInput",
  "AppFullWidth",
  "AppSelectTrigger",
  "AppPreviewSplit",
  "AppCanvasFrame",
] as const

export type AllowedAppChromeExport = (typeof ALLOWED_APP_CHROME_EXPORTS)[number]

/**
 * Relative paths under `src/` that are style owners (freehand Tailwind OK).
 * Everything else with UI is a feature surface.
 */
export const STYLE_OWNER_PATH_PREFIXES = [
  "components/app-chrome.tsx",
  "components/ui/",
  "index.css",
  "chamber-3d/scene-tokens.ts",
] as const

/** Non-UI modules that may exist under src without chrome imports. */
export const NON_UI_PATH_PREFIXES = [
  "domain/",
  "lib/",
  "ui/",
  "assets/",
] as const

/** Button variants allowed in feature code (shadcn names). */
export const ALLOWED_BUTTON_VARIANTS = [
  "default",
  "outline",
  "secondary",
  "ghost",
  "destructive",
  "link",
] as const

/** Role conventions (documentation + tests for known labels). */
export const BUTTON_ROLE_CONVENTIONS = {
  reset: "ghost",
  crossPageNav: "outline",
  primary: "default",
} as const
