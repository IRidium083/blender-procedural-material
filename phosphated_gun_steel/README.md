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
| Edge Width | AO distance in scene units; defaults to 0.045 |
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
