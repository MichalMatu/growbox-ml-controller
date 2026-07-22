import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { AppSectionTitle, AppMutedText } from "./typography"

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

export function AppCanvasFrame({ children }: { children: ReactNode }) {
  return (
    <div className="app-canvas-frame">
      <div className="app-canvas-frame-viewport">{children}</div>
    </div>
  )
}
