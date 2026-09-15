# Wood and plywood — planning

Status: placeholder and design notes only. No shader, script, or scene yet.

## Starting idea

Use Wave Texture for layers. Natural wood gets distorted waves and noise for
irregular grain; plywood gets evenly spaced waves for its manufactured layers.
Blender's Wave Texture supports bands, rings, and noise distortion, making it
a suitable starting point. [Wave Texture documentation](https://docs.blender.org/manual/en/5.2/render/shader_nodes/textures/wave.html)

## Solid wood

Proposed chain: physical coordinates → oriented/warped coordinates → Wave
Texture → Color Ramp → wood color, with restrained roughness and bump detail.

- Start with distorted **Bands** for a simple straight-grain board. Stretch the
  distortion noise along the grain so it meanders without becoming cloudy marble.
- For coherent side grain and end grain, use a shared 3D growth-ring field:
  cylindrical rings around a chosen trunk axis, with the board offset from its
  center. A cut across that axis shows rings; a longitudinal cut shows grain.
- Combine broad, low-frequency coordinate warping with much weaker fine noise.
  Expose growth-ring spacing separately from distortion amount and scale.
- Shape the wave with a Color Ramp to create narrow darker latewood and broader
  lighter earlywood. Avoid equal black/white zebra stripes.
- Add elongated fine noise for pores/fibers, mostly in roughness with shallow
  bump. Keep larger knots and species-specific structures for a later version.

## Plywood

- Align **Bands** with the panel's thickness axis and start with zero distortion.
  Keep layer boundaries straight and evenly spaced.
- Remap the wave into alternating veneer tones. Add very narrow optional glue
  lines; do not turn every interface into a deep groove.
- Keep layer structure separate from grain within each veneer. A layer index
  such as `floor(thickness_position_mm / ply_thickness_mm)` can alternate grain
  orientation by 90 degrees and introduce small per-layer color variation.
- Show exposed layers on cut edges. Broad outer faces should show a wood veneer
  grain pattern. For v1, use explicit face/edge material assignment or a supplied
  mask; automatic normal-based selection is an optional convenience and needs
  care on bevels and curved panels.
- Even waves describe the layer arrangement, not the entire surface appearance.
  Preserve wood grain within layers and on the outer veneer.

## Suggested module structure

| Module | Responsibility |
| --- | --- |
| Coordinates | Scene-unit conversion, grain axis, rotation, origin/seed |
| Wood structure | Distorted bands or growth rings; earlywood/latewood mask |
| Plywood structure | Ply spacing, layer index, glue lines, veneer/edge selection |
| Fine detail | Fibers, pores, subtle roughness and bump |
| Surface finish | Raw/sanded appearance initially; optional varnish later |

Suggested controls: Wood/Plywood mode, light/dark wood colors, grain direction,
ring spacing mm, distortion amount and size, pore strength, roughness, relief mm,
ply thickness mm, glue-line width mm, veneer grain scale, and Scene Unit m.

## Implementation sequence

1. Build with native shader nodes through `bpy`, following the root workflow.
   Keep Cycles and Eevee compatibility; OSL is not needed for these patterns.
2. Use explicit object coordinates converted to millimeters. Require applied
   object scale and avoid Generated coordinates for physical layer spacing.
3. Implement one natural-wood sample and one straight plywood edge sample.
   Calibrate Wave Scale against a known distance rather than assuming the node's
   Scale input is directly equal to repeats per millimeter.
4. Add the outer veneer and alternating internal grain. Keep an explicit mask
   input for complex meshes and plywood edge-banding.
5. Validate on a real-size board and a sample panel, for example 18 mm thick
   with a configurable 1.5 mm ply thickness (an artistic example, not a standard).
   Compare end grain, long grain, faces, edges, and bevels.
6. Check unchanged feature sizes across differently sized objects, unit conversion,
   distant-render aliasing, and both render engines. Pack any future image maps.

Use procedural detail first. Consider image textures later for distinctive knots,
species-specific pores, or close-up realism that the basic wave/noise model lacks.
Growth-ring spacing and plywood thickness are different parameters; neither should
change merely because the object becomes larger.


## Implemented v1

Added native shader-node material with Straight Grain, Growth Rings, and Plywood
modes; explicit veneer material assignment; alternating internal grain; thin glue
lines; and physical millimeter controls. All patterns are procedural.

Wave calibration uses the renderer's 20-times-coordinate phase and compensates
its sine-profile phase offset. Numeric EXR tests verify ring periods, layer tones,
glue masks, and centimeter-scene conversion. See Blender's implementation:
https://github.com/blender/blender/blob/main/intern/cycles/kernel/svm/wave.h

The gallery contains 240 mm boards and an 18 mm panel with 1.5 mm plies.
Natural wood uses broad and fine coordinate distortion, narrow latewood color,
and fine elongated noise for pore roughness and shallow relief.
Knots, species-specific anatomy and automatic face classification remain
future improvements. Distortion intentionally changes local ring spacing; the
spacing test checks the undistorted reference field.


## Shared clear finish update

Wood and FRP now consume shared/surface_finish.py. Clear Paint and Wax use a
Principled coat with independent top-surface normals; image scratches and
procedural smudges vary the coat, and dust is mixed over it. The scratch mask
is generated, stored once under shared/textures, and packed into both scenes.
Tests cover coat presets, disabled effects, smudge response and packed image data.


## Species-inspired presets

Added Pine, Maple, Oak, Walnut, Ebony and Custom using native menu routing.
Preset values do not mutate Custom inputs or shared coating controls. Added
elongated Voronoi vessel pores with diffuse/ring-concentrated distribution,
optional ray flecks, ring contrast, and resolved-parameter debug outputs.
The gallery compares five appearances and plywood; all remain artistic presets.
No additional image map was necessary for this version.


## Simplified material interfaces

1. Kept the approved species palettes and finish defaults. Retained the full
   structure group as Custom Wood for advanced authoring.
2. Created Pine, Maple, Oak, Walnut and Ebony Wood wrappers around that same
   master. Split plywood into Plywood Face and Plywood Edge; only the edge
   exposes physical ply thickness. Enabled fake users so Custom Wood survives
   saving without a preview object. No asset marking is used.
3. Reduced everyday inputs to Color Tint, Grain Scale, Grain Direction,
   Grain Detail, Finish, Surface Wear and Dust. The native finish menu uses
   None for raw wood. Maple retains its straight grain and softer wax coating.
4. Applied tint after solid/plywood color selection. Scaled only grain coordinates,
   keeping layer thickness and the shared surface finish in physical millimeters.
   Combined fine fiber color, roughness variation, pores, ray flecks and relief
   under Grain Detail; main ring contrast remains part of the species identity.
5. Combined image scratch strength and handling smudges under Surface Wear,
   preserving the previous default ratio. Kept dust independent. Hidden coating,
   pore and warp tuning stays inside the wrapper/master, with no duplicated
   structure or finish implementation. This is an interface simplification,
   not a claim of faster shader rendering.
6. Updated the Blender test to exercise public controls through temporary copied
   wrappers and rendered diagnostic outputs. Check palette/coat preservation,
   tint, detail, wear, dust, grain scaling/rotation, fixed ply scale, adjustable
   ply thickness, and scene-unit conversion alongside the original tests.
7. Regenerate wood.blend and the Cycles gallery, run test_material.py for numeric
   checks and Eevee, inspect both previews, and record results in validation.json.

For another material family, follow this pattern: keep a shared detailed core,
expose only controls that change the visible result in that wrapper, split
structurally different uses, and retain a clearly named advanced authoring material.


## Shared marks and final deposits

Separated masks from shader response in shared/surface_finish.py. Surface Marks
outputs scratches/smudges for material-specific shading before the BSDF. Surface
Deposits accepts the final shader and mixes dust above it, with optional external
coverage for metal cavities. Both use one procedural patch-field implementation.
Bakelite uses only procedural deposits, defaulting to zero dust. Regenerated the
four consuming blend files and tested material behavior plus arbitrary-shader
passthrough, full coverage and partial blending in Cycles and Eevee.
