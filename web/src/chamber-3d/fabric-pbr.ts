/**
 * Grow-tent PBR maps (static assets under public/textures/growtent/).
 * Interior: ambientCG Foil003 (CC0). Exterior: FreePBR nylon tent fabric.
 * See public/textures/growtent/ATTRIBUTION.md
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

/** Public paths (Vite serves `web/public` at `/`). */
export const GROWTENT_TEXTURE_URLS = {
  foil: {
    map: "/textures/growtent/foil_color.jpg",
    normalMap: "/textures/growtent/foil_normal.jpg",
    roughnessMap: "/textures/growtent/foil_rough.jpg",
    metalnessMap: "/textures/growtent/foil_metal.jpg",
    aoMap: "/textures/growtent/foil_ao.jpg",
  },
  nylon: {
    map: "/textures/growtent/nylon_color.jpg",
    normalMap: "/textures/growtent/nylon_normal.jpg",
    roughnessMap: "/textures/growtent/nylon_rough.jpg",
    metalnessMap: "/textures/growtent/nylon_metal.jpg",
    aoMap: "/textures/growtent/nylon_ao.jpg",
  },
} as const

export type PbrMapBundle = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
  metalnessMap: Texture
  aoMap: Texture
}

export type GrowtentPbrMaps = {
  interior: PbrMapBundle
  exterior: PbrMapBundle
}

function configureColorMap(texture: Texture): void {
  texture.colorSpace = SRGBColorSpace
  texture.wrapS = RepeatWrapping
  texture.wrapT = RepeatWrapping
  texture.repeat.set(1, 1)
  texture.magFilter = LinearFilter
  texture.minFilter = LinearMipmapLinearFilter
  texture.anisotropy = 8
  texture.needsUpdate = true
}

function configureDataMap(texture: Texture): void {
  texture.colorSpace = NoColorSpace
  texture.wrapS = RepeatWrapping
  texture.wrapT = RepeatWrapping
  texture.repeat.set(1, 1)
  texture.magFilter = LinearFilter
  texture.minFilter = LinearMipmapLinearFilter
  texture.anisotropy = 8
  texture.needsUpdate = true
}

/**
 * Load all growtent PBR maps once (must be under Suspense / Canvas).
 * Shared across panels — UV tiling lives on geometry, not texture.repeat.
 */
export function useGrowtentPbrMaps(): GrowtentPbrMaps {
  const foil = useTexture({
    map: GROWTENT_TEXTURE_URLS.foil.map,
    normalMap: GROWTENT_TEXTURE_URLS.foil.normalMap,
    roughnessMap: GROWTENT_TEXTURE_URLS.foil.roughnessMap,
    metalnessMap: GROWTENT_TEXTURE_URLS.foil.metalnessMap,
    aoMap: GROWTENT_TEXTURE_URLS.foil.aoMap,
  })
  const nylon = useTexture({
    map: GROWTENT_TEXTURE_URLS.nylon.map,
    normalMap: GROWTENT_TEXTURE_URLS.nylon.normalMap,
    roughnessMap: GROWTENT_TEXTURE_URLS.nylon.roughnessMap,
    metalnessMap: GROWTENT_TEXTURE_URLS.nylon.metalnessMap,
    aoMap: GROWTENT_TEXTURE_URLS.nylon.aoMap,
  })

  return useMemo(() => {
    configureColorMap(foil.map)
    configureDataMap(foil.normalMap)
    configureDataMap(foil.roughnessMap)
    configureDataMap(foil.metalnessMap)
    configureDataMap(foil.aoMap)

    configureColorMap(nylon.map)
    configureDataMap(nylon.normalMap)
    configureDataMap(nylon.roughnessMap)
    configureDataMap(nylon.metalnessMap)
    configureDataMap(nylon.aoMap)

    return {
      interior: foil as PbrMapBundle,
      exterior: nylon as PbrMapBundle,
    }
  }, [foil, nylon])
}
