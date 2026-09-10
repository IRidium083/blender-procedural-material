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

## Publishing reusable material assets

1. Create a material folder containing its generator, README, saved scene, and
   preview. Keep image maps in `textures/` and record their provenance in
   `textures/SOURCE.md`. Use Non-Color for numeric detail maps.
2. Build the node group with meaningful input names, sensible defaults, and
   bounded ranges. Reuse shared studio utilities where appropriate. For metal,
   keep machining detail subtle; choose color, roughness, and anisotropy before
   introducing visible bump. Match the technique to the intended finish.
3. Apply the material to a representative sample, render in Cycles, inspect it,
   and test Eevee where supported. Save the scene and keep its embedded generator
   synchronized with the source file. Keep texture dependencies packed.
4. Add a new scene to `SCENES` in `prepare_assets.py`, selecting its catalog and
   a representative PNG thumbnail. The existing two grip presets share their
   scene preview; use separate thumbnails if distinct preset previews are needed.
5. Run the asset preparation command below after generating or updating scenes.
   It marks material groups as assets, adds descriptions and tags, assigns stable
   catalog UUIDs, loads thumbnails, enables fake users, packs textures, and saves.
   It reopens every scene to verify metadata, thumbnails, and packed dependencies.
6. Inspect the assets in Blender's Asset Browser. Refresh the library after
   updates. Commit scripts, documentation, catalog definitions, textures, scenes,
   and previews together. Avoid committing Blender backup files.

```powershell
& $blender --factory-startup -b --python-exit-code 1 -P prepare_assets.py
```

The preparation script works on saved scenes and does not change Blender user
preferences. It does not standardize existing controls or create extra finish
presets; those remain deliberate material authoring choices.

## Asset preparation log ? 2026-09-09

- Published five material assets across four existing scene files.
- Metals: Machined Metal; Phosphated Gun Steel - Slightly Used.
- Painted Surfaces: Worn Painted Metal.
- Plastics and Rubber: Textured Grip - Hard Polymer; Textured Grip - Hard Rubber.
- Used the existing scene renders for asset thumbnails and packed image maps.
- Reopened all four scenes: asset metadata, thumbnails, and packing checks passed.

API references: [asset operations](https://docs.blender.org/api/5.2/bpy.ops.asset.html)
and [catalog format](https://developer.blender.org/docs/features/asset_system/backend/asset_catalogs/).
