# How I build and test materials

I interact with Blender by writing Python scripts and running them through
Blender's command line. I do not manually click or connect nodes in the UI.

This workflow applies to all material folders. Texture use, preview geometry,
and available tests differ by material.

1. **Build nodes with `bpy`.** Each material's Python generator creates or
   reuses a material and builds its shader node group. `nodes.new(...)` adds
   nodes and `links.new(...)` connects sockets. Group inputs expose the finish
   controls in Blender's Shader Editor.
2. **Add surface detail.** Procedural textures and geometry masks drive the
   finish. Where image detail is useful, the script loads the included texture
   with `bpy.data.images.load(...)`, treats height/roughness maps as Non-Color
   data, and packs the image into the scene. Worn painted metal uses no images.
3. **Run Blender in the background.** I launch Blender with `-b` to open a scene
   and `-P` to run the generator. It applies the material to the target mesh.
   `--preview --render` builds the material's preview setup, saves its `.blend`,
   and renders a PNG. See each material's README for its command and behavior.
4. **Inspect and verify.** I inspect the PNG, adjust the script, and rerun it.
   Where a `test_material.py` exists, I also run it to check the saved scene or
   node setup and render comparisons. Not every material has a separate test.

Example for machined metal, from the project root in PowerShell:

```powershell
$blender = 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
& $blender --factory-startup -b machined_metal/machined_metal.blend --python-exit-code 1 -P machined_metal/machined_metal.py -- --preview --render
& $blender --factory-startup -b machined_metal/machined_metal.blend --python-exit-code 1 -P machined_metal/test_material.py
```

`--factory-startup` avoids loading personal startup settings and add-ons;
`--python-exit-code 1` makes script errors visible as command failures.
The generator changes the file on disk, so reopen it in Blender to see updates
if that scene was already open in the UI.

## Checklist for future materials

1. Create a material folder with its generator, README, saved scene, and preview.
   Store image maps in `textures/` and record their source in `textures/SOURCE.md`.
2. Expose meaningful group inputs with sensible defaults and bounded ranges.
   Choose color, roughness, anisotropy, or bump according to the intended finish.
3. Render a representative sample, inspect it, and test supported render engines.
4. Pack image dependencies and keep embedded scripts synchronized with source.
5. Save the scene, update documentation, and commit source and outputs together.
   Reuse materials through File > Append > the scene file > Material.


## Cycles rendering device

Preview generators call the root render_utils.configure_cycles helper. It chooses
OptiX first (RTX 4070 on this workstation), then other available GPU backends,
and falls back to CPU when none is available. It enables only the chosen backend's
GPU devices and saves the generated preview scene with GPU Compute. The helper
is embedded in newly generated blends for Text Editor regeneration.

Machine-wide Cycles device preferences were saved as OptiX without replacing the
startup scene. Existing open sessions may need to reload those preferences.
Previously saved material blends retain their device setting until regenerated.
Small numerical validation scenes stay on CPU to avoid GPU setup overhead.
