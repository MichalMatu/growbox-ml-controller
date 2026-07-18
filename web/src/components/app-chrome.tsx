import type { ComponentProps, ReactNode } from "react"

import { Label } from "@/components/ui/label"
import { SelectTrigger } from "@/components/ui/select"
import { cn } from "@/lib/utils"

/**
 * ============================================================================
 * ALLOWED APP CHROME — single source of layout/visual tokens for feature UI.
 * ============================================================================
 * Feature code MUST NOT invent Tailwind `className` / `style`. Compose only these
 * primitives + shadcn `ui/*` (no className on shadcn in feature files either).
 *
 * Catalog: `src/ui/allowed-surface.ts`
 * Enforced by: eslint + ui-consistency tests (pre-commit).
 * ============================================================================
 */

const PAGE_WIDTH_CLASS = {
  standard: "max-w-3xl",
  /** Preview / 3D pages — width from --width-page-wide in index.css */
  wide: "app-page-wide",
} as const

export type AppPageWidth = keyof typeof PAGE_WIDTH_CLASS

// --- Page shell -------------------------------------------------------------

export function AppPage({
  width = "standard",
  children,
}: {
  width?: AppPageWidth
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        "mx-auto flex min-h-svh w-full min-w-0 flex-col gap-6 p-6",
        PAGE_WIDTH_CLASS[width],
      )}
    >
      {children}
    </div>
  )
}

export function AppPageHeader({
  title,
  badges,
  description,
  actions,
}: {
  title: ReactNode
  badges?: ReactNode
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {badges}
      </div>
      {description != null ? (
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
      ) : null}
      {actions != null ? <div>{actions}</div> : null}
    </header>
  )
}

export function AppPageFooter({ children }: { children: ReactNode }) {
  return <footer className="pb-8 text-xs text-muted-foreground">{children}</footer>
}

export function AppPageLoading({ children }: { children?: ReactNode }) {
  return (
    <AppPage>
      <div className="flex flex-1 items-center justify-center py-24 text-sm text-muted-foreground">
        {children ?? "Ładowanie…"}
      </div>
    </AppPage>
  )
}

// --- Typography / text ------------------------------------------------------

export function AppMutedText({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>
}

export function AppFieldMetaText({ children }: { children: ReactNode }) {
  return <p className="text-xs text-muted-foreground">{children}</p>
}

export function AppSectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-lg font-medium">{children}</h2>
}

export function AppSubsectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-medium text-foreground">{children}</h3>
}

// --- Stacks / structure -----------------------------------------------------

export function AppSection({ children }: { children: ReactNode }) {
  return <section className="flex flex-col gap-3">{children}</section>
}

export function AppSectionIntro({
  title,
  description,
}: {
  title: ReactNode
  description?: ReactNode
}) {
  return (
    <div>
      <AppSectionTitle>{title}</AppSectionTitle>
      {description != null ? <AppMutedText>{description}</AppMutedText> : null}
    </div>
  )
}

export function AppStack({
  gap = "md",
  children,
}: {
  gap?: "sm" | "md" | "lg"
  children: ReactNode
}) {
  const gapClass = gap === "sm" ? "gap-2" : gap === "lg" ? "gap-4" : "gap-3"
  return <div className={cn("flex flex-col", gapClass)}>{children}</div>
}

export function AppActionRow({
  children,
  align = "start",
}: {
  children: ReactNode
  /** Secondary form actions often sit end (e.g. Reset bottom-right). */
  align?: "start" | "end"
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap gap-2",
        align === "end" ? "justify-end" : "justify-start",
      )}
    >
      {children}
    </div>
  )
}

/** Card body: form fields grid or vertical action stack. */
export function AppCardBody({
  variant = "form",
  children,
}: {
  variant?: "form" | "stack"
  children: ReactNode
}) {
  return (
    <div className={variant === "form" ? "grid gap-4" : "flex flex-col gap-4"}>
      {children}
    </div>
  )
}

// --- Form controls ----------------------------------------------------------

/**
 * Compact multi-column field layout (e.g. W×D / H×volume).
 * Children should be AppFormField (or equivalent); cells get min-width:0.
 */
export function AppFormGrid({
  columns = 2,
  children,
}: {
  columns?: 2
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        "grid min-w-0 gap-3",
        columns === 2 && "grid-cols-2",
        "*:min-w-0",
      )}
    >
      {children}
    </div>
  )
}

export function AppFormField({
  label,
  htmlFor,
  end,
  children,
}: {
  label: ReactNode
  htmlFor: string
  /** Optional trailing control on the label row (e.g. compact Badge). */
  end?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="grid min-w-0 gap-2">
      {end != null ? (
        <div className="flex min-w-0 items-center justify-between gap-2">
          <Label htmlFor={htmlFor}>{label}</Label>
          {end}
        </div>
      ) : (
        <Label htmlFor={htmlFor}>{label}</Label>
      )}
      {children}
    </div>
  )
}

/** Bordered control block used by schema feature editors. */
export function AppControlSurface({
  variant = "stack",
  children,
}: {
  variant?: "stack" | "row"
  children: ReactNode
}) {
  if (variant === "row") {
    return (
      <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-3">
        {children}
      </div>
    )
  }
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">{children}</div>
  )
}

export function AppControlLabelBlock({ children }: { children: ReactNode }) {
  return <div className="space-y-1">{children}</div>
}

export function AppFieldStack({ children }: { children: ReactNode }) {
  return <div className="space-y-2">{children}</div>
}

export function AppErrorList({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null
  return (
    <ul className="list-disc space-y-1 rounded-lg border border-destructive/40 bg-destructive/5 p-3 pl-6 text-sm text-destructive">
      {errors.map((error) => (
        <li key={error}>{error}</li>
      ))}
    </ul>
  )
}

export function AppHiddenFileInput(props: ComponentProps<"input">) {
  // Strip style overrides so feature code cannot smuggle layout through the input.
  const { className: _ignoredClassName, style: _ignoredStyle, ...rest } = props
  void _ignoredClassName
  void _ignoredStyle
  return <input {...rest} type="file" className="hidden" />
}

export function AppFullWidth({ children }: { children: ReactNode }) {
  return <div className="w-full">{children}</div>
}

/** Full-width select trigger — strips caller className/style. */
export function AppSelectTrigger(props: ComponentProps<typeof SelectTrigger>) {
  const { className: _ignoredClassName, style: _ignoredStyle, ...rest } = props
  void _ignoredClassName
  void _ignoredStyle
  return <SelectTrigger {...rest} className="w-full" />
}

// --- Preview / media layouts ------------------------------------------------

/**
 * Side panel + main preview (wide pages only).
 * Layout lengths come from CSS tokens (--width-preview-sidebar); see index.css.
 * Sidebar and main are wrapped so long content cannot blow out the grid track.
 */
export function AppPreviewSplit({
  sidebar,
  main,
}: {
  sidebar: ReactNode
  main: ReactNode
}) {
  return (
    <div className="app-preview-split">
      <div className="app-preview-split-sidebar">{sidebar}</div>
      <div className="app-preview-split-main">{main}</div>
    </div>
  )
}

/**
 * Flush media/canvas surface.
 * Height comes from CSS (index.css): stacked → --height-canvas-frame;
 * side-by-side with AppPreviewSplit → stretch to match the sidebar column.
 */
export function AppCanvasFrame({ children }: { children: ReactNode }) {
  return (
    <div className="app-canvas-frame">
      <div className="app-canvas-frame-viewport">{children}</div>
    </div>
  )
}
