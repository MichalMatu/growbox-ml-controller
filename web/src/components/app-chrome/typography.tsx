import type { ReactNode } from "react"

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
