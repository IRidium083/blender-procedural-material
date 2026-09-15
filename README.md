# Procedural materials

See [WORKFLOW.md](WORKFLOW.md) for how I build and test materials through Blender.

Blender 5.2 materials with editable shader node groups. See each material guide
for controls and any bundled texture assets.


| Material | Files | Preview |
| --- | --- | --- |
| Bakelite (two procedural patterns) | [Controls and reference notes](bakelite/README.md) | [Cycles gallery](bakelite/bakelite_preview.png) |
| Fiberglass reinforced plastic | [Controls and usage](glassfiber/README.md) | [Cycles gallery](glassfiber/glassfiber_preview.png) |
| Procedural wood and plywood | [Controls and design](wood/README.md) | [Cycles gallery](wood/wood_preview.png) |
| Unified modular metal | [Presets and design](unified_metal/README.md) | [Cycles gallery](unified_metal/unified_metal_preview.png) |
| Worn painted metal | [Guide and controls](worn_painted_metal/README.md) | [Cycles](worn_painted_metal/recessed_metal_cycles.png) |
| Machined metal | [Guide and controls](machined_metal/README.md) | [Cycles](machined_metal/machined_metal_preview.png) |
| Textured plastic / hard rubber grip | [Guide and presets](textured_grip/README.md) | [Preview](textured_grip/textured_grip_preview.png) |
| Phosphated gun steel | [Guide and controls](phosphated_gun_steel/README.md) | [Preview](phosphated_gun_steel/phosphated_gun_steel_preview.png) |
| Oily polished machinery steel | [Guide and controls](oily_polished_steel/README.md) | [Preview](oily_polished_steel/oily_polished_steel_preview.png) |

Each material folder contains its generator, saved `.blend`, and render previews.
Painted metal and machined metal also include test scripts. Open its `.blend` to inspect or append the material, or open
the generator in Blender's Text Editor and run it with a mesh selected.
Keep this folder structure when running generators.

Shared root files:

- `test.blend`: reusable base scene for generating previews.
- `preview_utils.py`: common studio lights, camera placement, and render settings.
- `shared/resin_finish.py`: procedural molded-resin shading and optional deposits for both Bakelite patterns.
- `shared/surface_finish.py`: shared surface marks, shader-in/shader-out deposits and material finish adapters.
- `.gitignore` and `.gitattributes`: repository settings.

Run these commands from this project root in PowerShell:

```powershell
$blender = 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
& $blender --factory-startup -b test.blend --python-exit-code 1 -P machined_metal/machined_metal.py -- --preview --render
& $blender --factory-startup -b machined_metal/machined_metal.blend --python-exit-code 1 -P machined_metal/test_material.py
& $blender --factory-startup -b worn_painted_metal/worn_painted_metal.blend --python-exit-code 1 -P worn_painted_metal/test_material.py
```

Preview generation adjusts the sample's bevel, lights, and camera. Painted-metal
testing updates its saved scene and renders Cycles, Eevee, and a clean comparison.
Machined metal testing renders Eevee without changing the saved Cycles scene.
