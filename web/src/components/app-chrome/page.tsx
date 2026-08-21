import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

const PAGE_WIDTH_CLASS = {
  standard: "max-w-3xl",
  wide: "app-page-wide",
} as const

export type AppPageWidth = keyof typeof PAGE_WIDTH_CLASS

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
