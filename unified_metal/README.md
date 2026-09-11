# Unified Metal v1

Three modular stages with native Blender 5.2 dropdowns:
**base metal → surface finish → imperfections**. No add-on installation needed.
Coatings, plating removal, and substrate reveal are reserved for a future version.

![Six material combinations in Cycles](unified_metal_preview.png)

## Use

Open `unified_metal.blend`, select a sample, and open the Shader Editor. Its
**Unified Metal** group has four organized panels. Dropdown values are real
named menu choices, not numeric codes. You can also append the marked material
assets using File → Append → unified_metal.blend → Material.

For another scene, open `unified_metal.py` in the Text Editor, select one or more
meshes, and Run Script. It assigns one shared material to the selected meshes;
make a material single-user if you want different settings per object.
Enter the main group to inspect the three submodules and shader assembly.

| Panel / control | Choices or purpose |
| --- | --- |
| Base Metal | Steel, Aluminum, Bronze, Copper, Custom |
| Custom Metal Color | Only controls appearance when Base Metal is Custom |
| Finish | Polished, Brushed, Cast, Stonewashed, Machined, Custom |
| Texture Size | Fine (0.15 mm), Medium (0.5 mm), Coarse (1.2 mm), Custom |
| Custom Grain mm | Texture size when Texture Size is Custom |
| Custom Roughness / Relief / Anisotropy | Used when Finish is Custom |
| Direction Rotation | Euler rotation in radians for finish coordinates |
| Finish Seed | Change pattern placement without changing its size |
| Wear Level | None, Light, Moderate, Heavy, Custom |
| Custom Wear | Used when Wear Level is Custom |
| Wear Width mm | Width of convex edge polish |
| Scratches + Amount / Width / Depth | Independent toggle and scratch controls |
| Dust + Amount / Color / Spread | Independent cavity and upward-surface deposits |
| Oil + Amount / Tint / Patch size | Independent oily wipe stains |
| Imperfection Seed | Separate pattern placement for surface contamination |
| Scene Unit m | Meters per Blender unit; initialized from the scene on creation |
| View | Material, Roughness, Wear Mask, Scratch Mask, Dust Mask, Oil Mask |

**Preset mode does not overwrite Custom inputs.** Switching back to Custom
restores their effect. Custom finish currently uses isotropic grain, with manual
roughness, relief and anisotropy. Brush and turning-pattern orientation remains
an independent control. Custom controls may remain visible while inactive.

## Scale and behavior

Use consistently applied object scale: coordinates are object-space, converted
to millimeters. Mesh dimensions and scene unit scale determine physical texture
size. The sample blocks are 48 × 44 × 36 mm. Set Scene Unit m again if you later
change the scene's unit scale. Nonuniform unapplied scale stretches the texture.

Wear polishes convex edges and smooths their relief; scratches cut into the
current finish. Neither exposes another substrate. Dust is a rough nonmetallic
surface mixed over the metal. Oil tints the reflective surface and adds a glossy
optical film. Its internal Principled coat input is a lubricant approximation,
not the deferred manufacturing-coating or reveal system.

Default order: finish → wear/scratches → oil → dust. Dust covers oil where masks
overlap. Effects are independent: Wear Level=None does not disable Scratches,
Dust or Oil. Disable each toggle for a pristine surface.

Brushed grain follows local X; machined bands wrap around local Z. Direction
Rotation rotates the sampling coordinates. Complex tool paths, general radial
machining and object-specific tangents are outside this first version.

Metal colors and finish values are artistic presets, not measured alloy spectra.
There is no rust or oxide chemistry, bulk deformation, coating removal, or
silhouette displacement. Fine relief is bump shading.

## Texture and compatibility

The only image is `textures/oil_smear_mask.png`, reused from this project's oily
steel material. It uses Non-Color data and blended box projection, and is packed
in the blend. All other patterns and masks are nodes. No UV unwrap required.
Keep `textures/` beside the standalone script. Rebuilding from the supplied
blend can use its packed image even without the external PNG. See
[texture provenance](textures/SOURCE.md).

Cycles is the reference renderer. Eevee can render the gallery, but cavity/edge
AO and directional reflections can differ. AO needs real geometry and can be
affected by neighboring surfaces; bump scratches cannot generate AO cavities.
No add-on, update handler, or Python execution is needed to use the saved menus.

## Regenerate and test

From this folder in PowerShell:

```powershell
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $blender --factory-startup -b ../test.blend --python-exit-code 1 -P unified_metal.py -- --preview --render
& $blender --factory-startup -b unified_metal.blend --python-exit-code 1 -P test_material.py -- --render-eevee
```

The generator creates a separate gallery scene and embeds its source in the
saved blend. It leaves `test.blend` unchanged. The test reads the embedded source,
checks actual menu-driven shader values through small EXR renders, verifies
Custom preservation and disabled masks, and writes `validation.json`. It can
also render `unified_metal_eevee.png`; it does not overwrite the saved scene.

Gallery, back row: Steel/Polished, Aluminum/Brushed, Bronze/Cast with dust.
Front row: Copper/Stonewashed, Steel/Machined with oil, Custom with dust and oil.

See [DESIGN_LOG.md](DESIGN_LOG.md) for the accepted design and future roadmap.
