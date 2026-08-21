import type { ComponentProps, ReactNode } from "react"

import { Label } from "@/components/ui/label"
import { SelectTrigger } from "@/components/ui/select"
import { cn } from "@/lib/utils"

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
        "grid min-w-0 items-start gap-x-3 gap-y-3",
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
  end?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="grid min-w-0 gap-2">
      <div className="flex h-5 min-w-0 items-center justify-between gap-2">
        <Label htmlFor={htmlFor}>{label}</Label>
        {end != null ? end : null}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

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

export function AppFullWidth({ children }: { children: ReactNode }) {
  return <div className="w-full">{children}</div>
}

export function AppSelectTrigger(props: ComponentProps<typeof SelectTrigger>) {
  const { className: _ignoredClassName, style: _ignoredStyle, ...rest } = props
  void _ignoredClassName
  void _ignoredStyle
  return <SelectTrigger {...rest} className="w-full" />
}

export function AppHiddenFileInput(props: ComponentProps<"input">) {
  const { className: _ignoredClassName, style: _ignoredStyle, ...rest } = props
  void _ignoredClassName
  void _ignoredStyle
  return <input {...rest} type="file" className="hidden" />
}
