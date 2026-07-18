import { useSyncExternalStore } from "react"

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("popstate", onStoreChange)
  return () => window.removeEventListener("popstate", onStoreChange)
}

function getPathname(): string {
  return window.location.pathname
}

/** Client-side navigation for the static SPA (no router library). */
export function navigate(to: string): void {
  if (window.location.pathname === to) return
  window.history.pushState({}, "", to)
  window.dispatchEvent(new PopStateEvent("popstate"))
}

export function usePathname(): string {
  return useSyncExternalStore(subscribe, getPathname, () => "/")
}

export const ROUTES = {
  configurator: "/",
  chamber3d: "/chamber-3d",
} as const
