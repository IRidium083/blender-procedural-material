# Procedural wood and plywood

Native Blender 5.2 shader nodes with no images, UVs, OSL, or add-ons required.

![Wood and plywood gallery](wood_preview.png)

Open `wood.blend` to inspect or append these materials:

- **Procedural Wood**: warped 3D growth rings, including coherent end grain.
- **Straight Grain Wood**: distorted wave bands with elongated fine fibers.
- **Plywood Edge**: evenly spaced plies, alternating grain direction, thin glue lines.
- **Plywood Veneer**: lighter straight grain for the panel's outer faces.

The gallery shows growth-ring wood at the back, straight-grain wood in the middle,
and plywood at the front. Boards are 240 mm long; plywood is 18 mm thick.

## Controls and placement

| Control | Meaning |
| --- | --- |
| Structure | Straight Grain, Growth Rings, or Plywood |
| Light / Dark Wood | Earlywood and latewood colors |
| Ring Spacing mm | Undistorted wave/ring period |
| Distortion mm / Size mm | Natural grain warp amplitude and broad noise size |
| Grain Rotation | Euler rotation in radians; default grain runs along local X |
| Ring Center Offset mm | Offset the board relative to the growth-ring field |
| Seed | Shift grain without changing its physical scale |
| Roughness / Pore Strength | Base roughness and fine fiber roughness variation |
| Relief mm | Shallow fiber bump distance; zero disables relief |
| Ply Thickness mm | Each veneer layer's thickness; default 1.5 mm |
| Glue Width mm | Total thin boundary-line width; zero disables it |
| Veneer Face | 0 shows exposed plywood layers; 1 shows only wood grain |
| Scene Unit m | Meters per Blender unit; defaults to scene Unit Scale |

Apply scale with **Ctrl+A > Scale**. Object coordinates are converted to mm, so
larger objects contain more repeats without enlarging the grain. Leave Scene Unit m
at 1 for ordinary meter-based scenes, even when lengths display in centimeters.
After appending to a scene with another Unit Scale, update this input.

Growth rings surround local X before Grain Rotation. Plywood layers always follow
local Z, independently of grain rotation. Put the lower panel face at local Z=0
for full layers aligned with its boundary, as in the supplied panel. Its top and
bottom polygons use Plywood Veneer; cut edges use Plywood Edge. Assign these slots
explicitly to your own panel. A linked mask can drive Veneer Face on custom meshes.

Controls are artistic defaults, not measured species properties. Broad and fine
warping break up the rings; large knots and detailed species anatomy are not yet
modeled. Plywood uses fixed alternating base tones with wood-color modulation.
Relief is subtle bump only; no geometry displacement or automatic edge detection.

## Generate and test

Run from the project root in PowerShell:

```powershell
$blender = 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
& $blender --factory-startup -b --python-exit-code 1 -P wood/wood.py -- --preview --render
& $blender --factory-startup -b wood/wood.blend --python-exit-code 1 -P wood/test_material.py
```

Or run `wood.py` in Blender's Text Editor with a mesh selected to assign the
solid-wood material. The preview option creates a separate gallery scene and saves
`wood.blend` and `wood_preview.png` beside the generator. It embeds the script.
The test renders numeric EXRs to check physical ring and ply spacing, unit
conversion and glue masks, verifies face assignments, and writes `wood_eevee.png`
and `validation.json`. It does not overwrite the saved gallery.

[Original plan and implementation notes](DESIGN_LOG.md).
