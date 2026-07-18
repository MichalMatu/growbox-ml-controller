/**
 * Grow-tent PBR maps (static assets under public/textures/growtent/).
 * Interior: ambientCG Foil003 (CC0). Exterior: FreePBR nylon tent fabric.
 * See public/textures/growtent/ATTRIBUTION.md
 *
 * Only maps actually bound on materials are loaded (no dead metalness on nylon).
 */

import { useMemo } from "react"
import { useTexture } from "@react-three/drei"
import {
  LinearFilter,
  LinearMipmapLinearFilter,
  NoColorSpace,
  RepeatWrapping,
  SRGBColorSpace,
  type Texture,
} from "three"

const base = import.meta.env.BASE_URL.replace(/\/$/, "")

/** Public paths (Vite serves `web/public` at `/`). */
export const GROWTENT_TEXTURE_URLS = {
  interior: {
    map: `${base}/textures/growtent/foil_color.jpg`,
    normalMap: `${base}/textures/growtent/foil_normal.jpg`,
    roughnessMap: `${base}/textures/growtent/foil_rough.jpg`,
    metalnessMap: `${base}/textures/growtent/foil_metal.jpg`,
    aoMap: `${base}/textures/growtent/foil_ao.jpg`,
  },
  exterior: {
    map: `${base}/textures/growtent/nylon_color.jpg`,
    normalMap: `${base}/textures/growtent/nylon_normal.jpg`,
    roughnessMap: `${base}/textures/growtent/nylon_rough.jpg`,
    aoMap: `${base}/textures/growtent/nylon_ao.jpg`,
  },
} as const

export type InteriorPbrMaps = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
  metalnessMap: Texture
  aoMap: Texture
}

export type ExteriorPbrMaps = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
  aoMap: Texture
}

export type GrowtentPbrMaps = {
  interior: InteriorPbrMaps
  exterior: ExteriorPbrMaps
}

function configureTexture(texture: Texture, isColor: boolean): void {
  texture.colorSpace = isColor ? SRGBColorSpace : NoColorSpace
  texture.wrapS = RepeatWrapping
  texture.wrapT = RepeatWrapping
  texture.repeat.set(1, 1)
  texture.magFilter = LinearFilter
  texture.minFilter = LinearMipmapLinearFilter
  texture.anisotropy = 8
  texture.needsUpdate = true
}

function configureInterior(maps: InteriorPbrMaps): void {
  configureTexture(maps.map, true)
  configureTexture(maps.normalMap, false)
  configureTexture(maps.roughnessMap, false)
  configureTexture(maps.metalnessMap, false)
  configureTexture(maps.aoMap, false)
}

function configureExterior(maps: ExteriorPbrMaps): void {
  configureTexture(maps.map, true)
  configureTexture(maps.normalMap, false)
  configureTexture(maps.roughnessMap, false)
  configureTexture(maps.aoMap, false)
}

/**
 * Load growtent PBR maps once (must be under Suspense / Canvas).
 * Shared across panels — UV tiling lives on geometry, not texture.repeat.
 */
export function useGrowtentPbrMaps(): GrowtentPbrMaps {
  const interior = useTexture({ ...GROWTENT_TEXTURE_URLS.interior })
  const exterior = useTexture({ ...GROWTENT_TEXTURE_URLS.exterior })

  return useMemo(() => {
    const interiorMaps = interior as InteriorPbrMaps
    const exteriorMaps = exterior as ExteriorPbrMaps
    configureInterior(interiorMaps)
    configureExterior(exteriorMaps)
    return { interior: interiorMaps, exterior: exteriorMaps }
  }, [interior, exterior])
}
