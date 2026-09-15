# Shared surface imperfections

`surface_finish.py` separates reusable patterns from the way each material
responds to them. All are ordinary Blender shader node groups, cached by name
and version within a file. Their source is embedded in the consuming blend files.

## Surface Marks: before the BSDF

**Shared - Surface Marks v1** takes millimeter coordinates, scratch amount/tile
size, smudge amount/size and seed. It outputs **Scratch Mask** and **Smudge Mask**.
It has no shader output and makes no assumptions about metal, wood or a coat.

Scratches use the existing packed Non-Color image with blended box projection.
Smudges use **Shared - Surface Patch Field v1**, a procedural field also reused
by dust coverage. See [scratch provenance](textures/SOURCE.md).

Consumers choose the response:

- Wood/FRP: **Shared - Clear Finish Response v3** uses marks in Principled coat
  roughness and the separate coat normal, preserving substrate texture.
- Unified metal: its adapter uses marks in bare-metal roughness and shallow bump.
  Convex-edge polish and the existing image-based oil response remain metal-specific.
- Bakelite: retains fully procedural patterns and resin skin; it does not instantiate
  Surface Marks or load a scratch image.

## Surface Deposits: after the final shader

**Shared - Surface Deposits v1** accepts a **Surface** shader and returns **Shader**.
It mixes independent rough, nonmetallic dust over the incoming surface.

```text
Final wood / metal / plastic shader --> Surface Deposits --> Material Output
```

| Input | Meaning |
| --- | --- |
| Surface | Any finished surface shader, including a Mix Shader result |
| Coordinates mm | Object coordinates converted to physical millimeters |
| Dust | Procedural upward-biased dust amount; default 0 |
| Patch Size mm | Physical patch size, default 18 mm |
| Seed | Placement seed, default 4 |
| Additional Coverage | Optional external deposit mask, combined using Maximum |
| Dust Color | Deposit color, independent of incoming material |
| Dust Normal | Optional normal; unconnected zero uses the geometry normal |

Outputs are **Shader** and **Dust Mask**. With Dust and Additional Coverage both
zero, the incoming shader passes through unchanged. Coverage 1 fully replaces it
with the deposit shader. Additional Coverage is independent of Dust; clear both
for a guaranteed bypass. Values are clamped to 0-1.

**Shared - Deposit Coverage v1** generates the coverage independently. Unified
metal uses it upstream to combine ordinary surface dust with geometry-dependent
cavity accumulation, then supplies the combined mask to Additional Coverage on
the final Surface Deposits group. Wood, FRP and Bakelite use the group's internal
coverage directly. This avoids sending outputs back into their own upstream
shader graph.

To use elsewhere, append the group from NodeTree in a generated material blend.
Connect the previous shader to Surface and Shader to Material Output > Surface.
Connect Texture Coordinate > Object through Vector Math Scale using
`1000 * scene Unit Scale` to Coordinates mm. Apply object scale. Set Dust above 0.
No Python is required to render appended groups.

This group does not inspect or rewrite the incoming shader's roughness, color or
normal. Scratches that modify those properties belong before the BSDF. Oil remains
in the metal response instead of treating a shader mix as a physically complete
lubricant layer. The deposit model has no volumetric buildup or silhouette change.

## Resin surface

`resin_finish.py` builds **Shared - Molded Resin Surface v2**, used by both Bakelite
families. It combines nonmetallic resin, uneven roughness, microscopic mold-skin
bump, an optional polished reflection and the same final Surface Deposits group.
Its Dust control defaults to 0, preserving the original Bakelite look. This path
is entirely procedural and does not load the scratch texture.

## Regeneration and validation

When shared code changes, regenerate the consuming wood, glassfiber, unified_metal
and bakelite blend files. Existing embedded node trees do not update automatically.
Increment a group's version when changing its implementation or interface.
Clear Finish v3 replaces the old combined v2 group; the material-level wood/FRP
controls retain their names and defaults.

`attach_finish(graph, principled, coordinates_mm, units, defaults=None)` is the
wood/FRP adapter. It builds marks and coat response before shading, then returns
Surface Deposits after shading. The graph API is node/input/output/set/tree.
The Bakelite resin builder accepts its caller's Graph class.

Run the material tests, plus this shared test from the repository root:

```powershell
$blender = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe'
& $blender --factory-startup -b --python-exit-code 1 -P shared/test_surface_finish.py
```

The shared test uses actual Cycles and Eevee renders to verify zero-coverage
passthrough for emission, metal and mixed shaders, full replacement, and partial
coverage blending. Results are recorded in shared/validation.json. Material tests
cover physical scale, masks, presets and existing appearance controls.
