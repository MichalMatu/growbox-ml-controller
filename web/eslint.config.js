import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import { defineConfig, globalIgnores } from "eslint/config"

const noFreehandStylesMessage =
  "Feature UI may not invent or override styles. Compose @/components/app-chrome + shadcn ui/* without className/style. Edit app-chrome.tsx or components/ui to change look."

/** Shared AST bans for feature surfaces (no freehand styling). */
const featureSurfaceRestrictedSyntax = [
  {
    selector:
      "JSXOpeningElement[name.name='Button'] > JSXAttribute[name.name='size']:not([value.value='icon']):not([value.expression.value='icon'])",
    message:
      "Do not set Button size for text buttons. Omit size (default only). size=\"icon\" is allowed for square icon-only buttons.",
  },
  {
    // Any className attribute — string, expression, or variable
    selector: "JSXAttribute[name.name='className']",
    message: noFreehandStylesMessage,
  },
  {
    selector: "JSXAttribute[name.name='style']",
    message: noFreehandStylesMessage,
  },
  {
    selector: "CallExpression[callee.name='cn']",
    message: noFreehandStylesMessage,
  },
]

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ["src/components/ui/**/*.{ts,tsx}"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: [
      "src/lib/routing.ts",
      "src/components/app-chrome.tsx",
      "src/ui/allowed-surface.ts",
      "src/chamber-3d/scene-tokens.ts",
    ],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
  // Button size lock for everything except shadcn ui + style owners
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: [
      "src/components/ui/**",
      "src/components/app-chrome.tsx",
      "src/**/*.test.ts",
      "src/ui/**",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "JSXOpeningElement[name.name='Button'] > JSXAttribute[name.name='size']:not([value.value='icon']):not([value.expression.value='icon'])",
          message:
            "Do not set Button size for text buttons. Omit size (default only). size=\"icon\" is allowed for square icon-only buttons.",
        },
      ],
    },
  },
  // Feature surfaces: zero freehand className/style/cn
  {
    files: [
      "src/App.tsx",
      "src/app-router.tsx",
      "src/main.tsx",
      "src/pages/**/*.{ts,tsx}",
      "src/components/**/*.{ts,tsx}",
    ],
    ignores: ["src/components/ui/**", "src/components/app-chrome.tsx"],
    rules: {
      "no-restricted-syntax": ["error", ...featureSurfaceRestrictedSyntax],
    },
  },
  // chamber-3d scene files: no freehand DOM className/style; colors via resolveChamberSceneColors
  {
    files: ["src/chamber-3d/**/*.{ts,tsx}"],
    ignores: ["src/chamber-3d/scene-tokens.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='className'] Literal",
          message:
            "R3F DOM class strings belong in scene-tokens.ts (CHAMBER_CANVAS_CLASS).",
        },
        {
          selector:
            "JSXAttribute[name.name='className'] > JSXExpressionContainer > Literal",
          message:
            "R3F DOM class strings belong in scene-tokens.ts (CHAMBER_CANVAS_CLASS).",
        },
        {
          selector: "JSXAttribute[name.name='style']",
          message: "No inline style in chamber-3d; use scene-tokens or materials.",
        },
        {
          selector: "Literal[value=/^#(?:[0-9a-fA-F]{3,8})$/]",
          message:
            "No hex colors in chamber scene files. Use resolveChamberSceneColors() / CSS --chamber-* tokens.",
        },
      ],
    },
  },
  // app-chrome: no hex; lengths via CSS tokens / named classes only
  {
    files: ["src/components/app-chrome.tsx"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/^#(?:[0-9a-fA-F]{3,8})$/]",
          message: "No hex in app-chrome. Use theme CSS variables / index.css tokens.",
        },
        {
          selector: "Literal[value=/(?:70vh|16rem|h-\\[|minmax\\()/]",
          message:
            "No magic layout lengths in app-chrome. Use CSS tokens (--height-canvas-frame, --width-preview-sidebar-min) and named classes in index.css.",
        },
      ],
    },
  },
])
