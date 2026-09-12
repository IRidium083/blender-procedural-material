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
Knots, species-specific anatomy, varnish, and automatic face classification remain
future improvements. Distortion intentionally changes local ring spacing; the
spacing test checks the undistorted reference field.
