# Hammertone material construction

2026-09-16 — Blender 5.2.2 LTS.

1. Used a metallic painted finish as the target: millimeter-scale irregular cells,
   shallow relief and glossy binder. Chose a procedural structure because the
   pattern does not require photographed detail or UV layout.
2. Reused the shared node Builder, surface patch field and final shader deposits.
   Kept the existing shared module unchanged so other materials retain their look.
3. Converted object coordinates to mm using the scene unit scale, then divided
   by nominal cell size. Added seeded noise distortion before 3D Voronoi sampling.
4. Built rounded basins from cell distance, soft borders from distance-to-edge,
   and per-cell pigment variation. Routed color to Base Color and a 25 micrometer
   maximum relief to Bump, multiplied by Hammer Amount.
5. Added Principled metallic pigment and dielectric coat. Shared smudges alter
   both roughness responses; shared deposits wrap the finished shader. No scratches
   were added. Eight public inputs serve all three color presets.
6. Generated a physical-scale panel/sphere gallery in background Blender through
   `bpy`, using OptiX on the RTX 4070. Saved the blend before rendering the gallery
   and 34 mm close-up, with generator and helper sources embedded.
7. Inspected the first renders. The first distance-to-edge profile read too much
   like a crack network, so changed to radial rounded basins, softer borders and
   color gradients inside cells. Rebuilt and inspected the close-up.
8. Validated zero-effect controls, shallow relief, cell-size response, consistent
   geometry/texture scaling and centimeter scene units through numeric renders.
   Checked embedded-source fallback and rendered the final materials in Eevee.

To extend this material, first change preset values. Split the shader only if a
new paint process requires a different structure. Keep any future scratches in
the shared image-based surface marks module rather than synthesizing a separate
scratch system here.

## Reference-driven relief revision

Reviewed the three user-supplied pictures in `references/`. Their cell surfaces
break up reflections much more strongly than the first version, with additional
fine texture inside the cells. Increased nominal maximum relief from 0.025 mm to
0.160 mm (0.128 mm at the default Hammer Amount) and Bump strength from 0.7 to 1.
Added low-amplitude fine procedural paint texture to the same height field, so
Hammer Amount zero still removes all bump. Both the paint and coat normals use
this field. Reduced clean coat roughness from 0.16 to 0.12 to show the broken-up
highlights more clearly. These are visual choices; photo dimensions are unknown.

Kept the existing eight public controls and shared smudge/deposit modules.
Rebuilt the saved GPU Cycles gallery and adjusted only the close-up camera to
show reflection breakup. Updated the numeric relief check and reran validation.
