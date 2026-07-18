# Grow tent PBR textures

Only maps bound by `web/src/chamber-3d/fabric-pbr.ts` are shipped.

## Interior — foil / mylar

- **Source:** ambientCG [Foil003](https://ambientcg.com/view?id=Foil003)
- **License:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain)
- **Files:** `foil_color.jpg`, `foil_normal.jpg`, `foil_rough.jpg`, `foil_metal.jpg`, `foil_ao.jpg`
- **Maps:** Color, Normal (OpenGL), Roughness, Metalness, AO (1K JPG)

## Exterior — nylon tent fabric

- **Source:** FreePBR [Nylon Tent fabric](https://freepbr.com/product/nylon-tent-fabric1/)
- **License:** free for use as stated on FreePBR product page (credit appreciated)
- **Files:** `nylon_color.jpg`, `nylon_normal.jpg`, `nylon_rough.jpg`, `nylon_ao.jpg`
- **Maps:** Albedo, Normal (OpenGL), Roughness, AO (JPEG for web size)
- **Omitted:** metallic map (exterior is forced matte non-metal in materials)

Do not add texture files without wiring them in `fabric-pbr.ts` and updating this file.
