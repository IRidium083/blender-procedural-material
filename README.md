# Procedural materials

Blender 5.2 shader materials with editable node groups, no image textures required.

| Material | Files | Preview |
| --- | --- | --- |
| Worn painted metal | [Guide and controls](worn_painted_metal/README.md) | [Cycles](worn_painted_metal/recessed_metal_cycles.png) |
| Machined aluminum | [Guide and controls](machined_aluminum/README.md) | [Cycles](machined_aluminum/machined_aluminum_preview.png) |

Each material folder contains its generator, saved `.blend`, render previews,
and test script. Open its `.blend` to inspect or append the material, or open
the generator in Blender's Text Editor and run it with a mesh selected.
Keep this folder structure when running generators.

Shared root files:

- `test.blend`: reusable base scene for generating previews.
- `preview_utils.py`: common studio lights, camera placement, and render settings.
- `.gitignore` and `.gitattributes`: repository settings.

Run these commands from this project root in PowerShell:

```powershell
$blender = 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
& $blender --factory-startup -b test.blend --python-exit-code 1 -P machined_aluminum/machined_aluminum.py -- --preview --render
& $blender --factory-startup -b machined_aluminum/machined_aluminum.blend --python-exit-code 1 -P machined_aluminum/test_material.py
& $blender --factory-startup -b worn_painted_metal/worn_painted_metal.blend --python-exit-code 1 -P worn_painted_metal/test_material.py
```

Preview generation adjusts the sample's bevel, lights, and camera. Painted-metal
testing updates its saved scene and renders Cycles, Eevee, and a clean comparison.
Aluminum testing renders Eevee without changing the saved Cycles scene.
