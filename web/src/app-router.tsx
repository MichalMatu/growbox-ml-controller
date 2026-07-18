import { lazy, Suspense } from "react"

import { App } from "@/App"
import { ROUTES, usePathname } from "@/lib/routing"

/** R3F stays out of the configurator bundle until this route is opened. */
const Chamber3dPage = lazy(async () => {
  const module = await import("@/pages/chamber-3d-page")
  return { default: module.Chamber3dPage }
})

/** Thin shell: configurator at `/`, R3F playground at `/chamber-3d`. */
export function AppRouter() {
  const pathname = usePathname()

  if (pathname === ROUTES.chamber3d || pathname.startsWith(`${ROUTES.chamber3d}/`)) {
    return (
      <Suspense
        fallback={
          <div className="flex min-h-svh items-center justify-center p-6 text-sm text-muted-foreground">
            Ładowanie podglądu 3D…
          </div>
        }
      >
        <Chamber3dPage />
      </Suspense>
    )
  }

  return <App />
}
