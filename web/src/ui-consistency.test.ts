import { readFileSync, readdirSync, statSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

import {
  ALLOWED_APP_CHROME_EXPORTS,
  BUTTON_ROLE_CONVENTIONS,
  NON_UI_PATH_PREFIXES,
  STYLE_OWNER_PATH_PREFIXES,
} from "@/ui/allowed-surface"

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)))
const buttonSource = readFileSync(path.join(srcRoot, "components/ui/button.tsx"), "utf8")
const chromeSource = readFileSync(path.join(srcRoot, "components/app-chrome.tsx"), "utf8")
const sceneTokensSource = readFileSync(
  path.join(srcRoot, "chamber-3d", "scene-tokens.ts"),
  "utf8",
)

function walkSourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === "dist" || name.startsWith(".")) continue
    const full = path.join(dir, name)
    const st = statSync(full)
    if (st.isDirectory()) {
      out.push(...walkSourceFiles(full))
      continue
    }
    if (name.endsWith(".tsx") || name.endsWith(".ts")) out.push(full)
  }
  return out
}

function rel(file: string): string {
  return path.relative(srcRoot, file).split(path.sep).join("/")
}

function isStyleOwner(relativePath: string): boolean {
  return STYLE_OWNER_PATH_PREFIXES.some(
    (prefix) => relativePath === prefix || relativePath.startsWith(prefix),
  )
}

function isNonUi(relativePath: string): boolean {
  if (relativePath.endsWith(".test.ts") || relativePath.endsWith(".test.tsx")) return true
  return NON_UI_PATH_PREFIXES.some((prefix) => relativePath.startsWith(prefix))
}

/** Feature / product UI modules that must not freehand styles. */
function listFeatureSurfaces(): string[] {
  return walkSourceFiles(srcRoot)
    .map(rel)
    .filter((r) => !isStyleOwner(r) && !isNonUi(r))
    .filter((r) => !r.startsWith("chamber-3d/") || r === "chamber-3d/scene-tokens.ts")
    // chamber-3d scene implementations are checked separately for hex/class
    .filter((r) => !r.startsWith("chamber-3d/") || r.endsWith("scene-tokens.ts"))
}

function listChamberSceneFiles(): string[] {
  return walkSourceFiles(path.join(srcRoot, "chamber-3d"))
    .map(rel)
    .filter((r) => r !== "chamber-3d/scene-tokens.ts")
}

function readRel(relativePath: string): string {
  return readFileSync(path.join(srcRoot, relativePath), "utf8")
}

function freehandStyleHits(source: string): string[] {
  const hits: string[] = []
  // JSX attributes only (not `const style = document.createElement(...)`).
  if (/\bclassName\s*=/.test(source)) hits.push("className=")
  if (/<[^>]*\bstyle\s*=/.test(source)) hits.push("style=")
  if (/\bcn\s*\(/.test(source)) hits.push("cn(")
  return hits
}

function parseChromeComponentExports(source: string): string[] {
  const names = new Set<string>()
  for (const match of source.matchAll(/^export function ([A-Z][A-Za-z0-9]*)\b/gm)) {
    if (match[1]) names.add(match[1])
  }
  for (const match of source.matchAll(/^export const ([A-Z][A-Z0-9_]*)\b/gm)) {
    if (match[1]) names.add(match[1])
  }
  return [...names].sort()
}

describe("UI allowlist — design rules", () => {
  it("Button CVA exposes only default and icon sizes", () => {
    for (const forbidden of ["xs:", "sm:", "lg:", '"icon-xs"', '"icon-sm"', '"icon-lg"']) {
      expect(buttonSource.includes(forbidden), `button.tsx must not define size ${forbidden}`).toBe(
        false,
      )
    }
    expect(buttonSource).toMatch(/size:\s*\{[\s\S]*default:[\s\S]*icon:/)
  })

  it("allowed-surface catalog matches app-chrome exports bidirectionally", () => {
    const actual = parseChromeComponentExports(chromeSource)
    const allowed = [...ALLOWED_APP_CHROME_EXPORTS].sort()
    expect(actual, "app-chrome exports vs ALLOWED_APP_CHROME_EXPORTS").toEqual(allowed)
  })

  it("scene-tokens owns chamber canvas class and color hexes", () => {
    expect(sceneTokensSource).toMatch(/export const CHAMBER_CANVAS_CLASS/)
    expect(sceneTokensSource).toMatch(/export const CHAMBER_SCENE/)
    for (const file of listChamberSceneFiles()) {
      const text = readRel(file)
      const hexLiterals = text.match(/#[0-9a-fA-F]{3,8}/g) ?? []
      expect(hexLiterals, `${file} must not hardcode hex; use CHAMBER_SCENE`).toEqual([])
      if (/\bclassName\s*=\s*["'`]/.test(text)) {
        expect.fail(`${file} has string className; use CHAMBER_CANVAS_CLASS`)
      }
    }
  })
})

describe("UI allowlist — enforcement sieve", () => {
  it("every feature surface is free of className/style/cn", () => {
    const surfaces = listFeatureSurfaces().filter((r) => !r.startsWith("chamber-3d/"))
    expect(surfaces.length).toBeGreaterThan(0)

    const offenders: string[] = []
    for (const surface of surfaces) {
      const hits = freehandStyleHits(readRel(surface))
      for (const hit of hits) offenders.push(`${surface}: ${hit}`)
    }
    expect(offenders).toEqual([])
  })

  it("feature surfaces auto-include App, pages, feature-control, app-router", () => {
    const surfaces = new Set(listFeatureSurfaces())
    for (const required of [
      "App.tsx",
      "app-router.tsx",
      "pages/chamber-3d-page.tsx",
      "components/feature-control.tsx",
    ]) {
      expect(surfaces.has(required), `missing feature surface ${required}`).toBe(true)
    }
  })

  it("pages/* and App import app-chrome for shell", () => {
    expect(readRel("App.tsx")).toMatch(/from "@\/components\/app-chrome"/)
    expect(readRel("pages/chamber-3d-page.tsx")).toMatch(/from "@\/components\/app-chrome"/)
    expect(readRel("components/feature-control.tsx")).toMatch(/from "@\/components\/app-chrome"/)
    expect(readRel("app-router.tsx")).toMatch(/AppPageLoading/)
  })

  it("Reset uses ghost; cross-page nav uses outline; no size prop", () => {
    const resetVariant = BUTTON_ROLE_CONVENTIONS.reset
    const navVariant = BUTTON_ROLE_CONVENTIONS.crossPageNav

    for (const file of ["App.tsx", "pages/chamber-3d-page.tsx"]) {
      const text = readRel(file)
      const resetButtons = [...text.matchAll(/<Button\b[\s\S]*?>\s*Reset\s*<\/Button>/g)]
      expect(resetButtons.length, `${file} Reset`).toBeGreaterThan(0)
      for (const match of resetButtons) {
        expect(match[0]).toMatch(new RegExp(`variant\\s*=\\s*["']${resetVariant}["']`))
        expect(match[0]).not.toMatch(/\bsize\s*=/)
      }
    }

    const navPairs = [
      { file: "App.tsx", label: "Podgląd 3D" },
      { file: "pages/chamber-3d-page.tsx", label: "Wróć do konfiguratora" },
    ]
    for (const { file, label } of navPairs) {
      const text = readRel(file)
      const re = new RegExp(`<Button\\b[\\s\\S]*?>\\s*${label}[\\s\\S]*?<\\/Button>`)
      const match = re.exec(text)
      expect(match, label).not.toBeNull()
      expect(match![0]).toMatch(new RegExp(`variant\\s*=\\s*["']${navVariant}["']`))
      expect(match![0]).not.toMatch(/\bsize\s*=/)
    }
  })

  it("no text Button size overrides outside ui/", () => {
    const files = walkSourceFiles(srcRoot).filter((file) => {
      const r = rel(file)
      return !r.startsWith("components/ui/") && !r.endsWith(".test.ts")
    })

    const sizeOnButton =
      /<Button\b[^>]*\bsize\s*=\s*(?!(?:["']icon["']|\{["']icon["']\}))/s

    const offenders: string[] = []
    for (const file of files) {
      if (sizeOnButton.test(readFileSync(file, "utf8"))) offenders.push(rel(file))
    }
    expect(offenders).toEqual([])
  })

  it("sieve covers future pages without hardcoding (pages dir is dynamic)", () => {
    const pagesDir = path.join(srcRoot, "pages")
    const pageFiles = readdirSync(pagesDir).filter((n) => n.endsWith(".tsx"))
    const surfaces = new Set(listFeatureSurfaces())
    for (const name of pageFiles) {
      expect(surfaces.has(`pages/${name}`)).toBe(true)
      expect(freehandStyleHits(readRel(`pages/${name}`))).toEqual([])
    }
  })
})
