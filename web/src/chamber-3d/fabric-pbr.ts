/**
 * Grow-tent PBR maps (static assets + procedural).
 * Interior: ambientCG Foil003 (CC0) — static JPGs.
 * Exterior: procedural oxford twill weave — 600D fabric, replaces FreePBR nylon.
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

import {
  useOxfordPbrMaps,
  type OxfordPbrMaps,
} from "@/chamber-3d/oxford-pbr"

const base = import.meta.env.BASE_URL.replace(/\/$/, "")

/** Static PBR paths for interior foil (ambientCG Foil003, CC0). */
const FOIL_TEXTURE_URLS = {
  map: `${base}/textures/growtent/foil_color.jpg`,
  normalMap: `${base}/textures/growtent/foil_normal.jpg`,
  roughnessMap: `${base}/textures/growtent/foil_rough.jpg`,
  metalnessMap: `${base}/textures/growtent/foil_metal.jpg`,
  aoMap: `${base}/textures/growtent/foil_ao.jpg`,
} as const

export type InteriorPbrMaps = {
  map: Texture
  normalMap: Texture
  roughnessMap: Texture
  metalnessMap: Texture
  aoMap: Texture
}

/** Exterior = procedural oxford fabric (replaces old FreePBR nylon). */
export type ExteriorPbrMaps = OxfordPbrMaps

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

function configureFoil(maps: InteriorPbrMaps): void {
  configureTexture(maps.map, true)
  configureTexture(maps.normalMap, false)
  configureTexture(maps.roughnessMap, false)
  configureTexture(maps.metalnessMap, false)
  configureTexture(maps.aoMap, false)
}

/**
 * Load growtent PBR maps once (must be under Suspense / Canvas).
 * Interior = Foil003 JPGs. Exterior = procedural oxford twill weave.
 */
export function useGrowtentPbrMaps(): GrowtentPbrMaps {
  const foil = useTexture({ ...FOIL_TEXTURE_URLS })
  const oxford = useOxfordPbrMaps(512)

  return useMemo(() => {
    const interiorMaps = foil as InteriorPbrMaps
    configureFoil(interiorMaps)
    return { interior: interiorMaps, exterior: oxford }
  }, [foil, oxford])
}
