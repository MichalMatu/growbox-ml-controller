import { useMemo } from "react"
import { CHAMBER_MATERIAL, type ChamberSceneColors } from "@/chamber-3d/core/scene-tokens"

export function sceneIntensity(lit: boolean, on: number, powerScale: number): number {
  if (!lit) return CHAMBER_MATERIAL.lightOffSceneIntensity
  return on * powerScale
}


export function useLightMaterials(colors: ChamberSceneColors, lit: boolean) {
  return useMemo(
    () => ({
      housing: {
        color: colors.lightHousing,
        roughness: CHAMBER_MATERIAL.lightHousingRoughness,
        metalness: CHAMBER_MATERIAL.lightHousingMetalness,
        envMapIntensity: CHAMBER_MATERIAL.lightHousingEnvMapIntensity,
      },
      /** Specular aluminium inside HPS reflectors — no warm emissive wash. */
      reflector: {
        color: colors.lightDuct,
        roughness: 0.2,
        metalness: 0.9,
        envMapIntensity: 0.8,
      },
      board: {
        color: colors.lightHousing,
        roughness: 0.75,
        metalness: 0.25,
        envMapIntensity: 0.25,
      },
      diode: {
        color: colors.lightEmitter,
        roughness: 0.2,
        metalness: 0.05,
        emissive: colors.lightEmitter,
        emissiveIntensity: lit
          ? CHAMBER_MATERIAL.lightEmitterEmissiveOn
          : CHAMBER_MATERIAL.lightEmitterEmissiveOff,
      },
      duct: {
        color: colors.lightDuct,
        roughness: CHAMBER_MATERIAL.lightDuctRoughness,
        metalness: CHAMBER_MATERIAL.lightDuctMetalness,
        envMapIntensity: 0.85,
      },
      bulb: {
        color: colors.lightBulb,
        roughness: 0.18,
        metalness: 0.05,
        emissive: colors.lightBulb,
        emissiveIntensity: lit
          ? CHAMBER_MATERIAL.lightBulbEmissiveOn
          : CHAMBER_MATERIAL.lightBulbEmissiveOff,
      },
    }),
    [colors, lit],
  )
}
