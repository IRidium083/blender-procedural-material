# Slightly used phosphated gun steel

Dark charcoal, subtly green-gray phosphate finish with microscopic grain,
uneven matte roughness, restrained edge polishing, and sparse shallow scratches.
This is an artistic approximation of phosphated/Parkerized steel, with no
paint flakes or heavy rust. Hybrid shader: a single grayscale image supplies
irregular phosphate microrelief and subtle roughness variation. Color, scratches,
edge wear, and overall finish remain procedural and adjustable.

![Phosphated steel preview](phosphated_gun_steel_preview.png)

Open `phosphated_gun_steel.py` in Blender 5.2's Text Editor, select your meshes,
and Run Script. Adjust the material group in the Shader Editor. The separate
`.blend` includes a machined sample with a pocket, raised rib, and circular details,
plus studio lighting and an embedded copy of the script.

| Control | Purpose |
| --- | --- |
| Finish Color / Exposed Steel | Coated surface and polished steel colors |
| Roughness | Matte finish; defaults to 0.57 |
| Edge Wear | Restrained edge polish; zero disables it |
| Edge Width | AO distance in scene units; defaults to 0.0005 m |
| Scratches | Independent shallow abrasion; zero disables it |
| Grain Depth | Microscopic coating relief |
| Pattern Scale | Object-space texture frequency |
| Microdetail Tiling | Image repeats per object-space unit, multiplied by Pattern Scale |
| Micro Roughness | Strength of image-driven roughness variation; zero disables it |

`textures/phosphate_microdetail.png` is the only image texture. It is read as
**Non-Color**, repeated with blended box projection, and packed into the `.blend`.
No UV unwrap is required. Keep the textures folder next to the standalone script;
the supplied blend also works from its packed image when the external PNG is absent.
There are no separate color, metallic, scratch, edge-wear or normal-map images.
The image is an AI-generated artistic microdetail map, not a measured surface scan.
Generation prompt and provenance are recorded in `textures/SOURCE.md`.

Cycles is the reference renderer. The shader also uses Eevee-compatible nodes,
but Eevee's screen-space AO may change edge wear with the view. Use closed meshes,
outward normals and consistent object scale. The coating is a visual metallic
approximation, not a measured layered optical model.

From this folder, regenerate the preview (the source test scene is unchanged):

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b ../test.blend --python-exit-code 1 -P phosphated_gun_steel.py -- --preview --render
```

## Real dimensions

The shader now uses physical-size defaults. Apply object scale with **Ctrl+A >
Scale** before assigning the material, including after setting object dimensions.
Object coordinates use mesh-local dimensions; unapplied scale can stretch detail.
The material does not automatically normalize its texture to the object's bounds:
large parts show more repeats, while small parts retain the same feature size.

**Meters Per Unit** converts local coordinates into meters and converts bump/AO
lengths back into scene units. It defaults to Scene > Units > Unit Scale when the
material is generated. Leave it at **1** for ordinary meter-based Blender scenes,
even if the length display is centimeters. Use **0.01** only when Unit Scale is
0.01. After appending to a scene with different Unit Scale, update this input.
All depth and edge-width controls are entered in meters.

The saved steel sample is 0.28 m long. Pattern Scale defaults to 10;
Edge Width is 0.5 mm, Grain Depth is 0.01 mm, and Scratch Depth is 0.03 mm.
These are artistic shader settings, not measured coating specifications.
