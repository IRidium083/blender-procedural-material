# Unified Metal: design and implementation log

## 2026-09-11 — intent and scope

The user proposed a unified material built from three independently reusable
modules: base metal (steel, aluminum, bronze, etc.), surface finish (polished,
cast, brushed, stonewashed, etc.), and imperfections (wear, dust, stains, etc.).
The goal is to combine presets without duplicating whole material generators.

The initial discussion distinguished a surface finish from an added coating.
The user explicitly deferred coating and substrate-reveal behavior because it
would make the first version too complex. This is a future plan, not part of v1.

The user also asked for named dropdown presets instead of entering every value
manually. We agreed to native shader-group menus, coordinated preset values,
independent imperfection toggles, and Custom overrides that preserve manual
settings while a preset is active. Implementation was then authorized together
with this local record of the discussion.

## Architecture chosen

1. **Base Metal:** menu selects reflective metal color, with a constant metallic
   substrate. Custom selects the saved custom color.
2. **Surface Finish:** menu selects roughness, grain relief, and anisotropy.
   A separate size menu selects grain dimensions. Brushed and machined finishes
   have directional sampling; cast and stonewashed finishes use isotropic detail.
3. **Imperfections:** shared convex/cavity masks drive edge polish and deposits.
   Independent scratch, dust and oil controls modify the surface. This module
   outputs explicit masks and surface channels for inspection and composition.
4. **Assembly:** combine height into one bump normal; build finished metal;
   apply oil response; mix nonmetallic dust over the result. A debug menu displays
   roughness and masks. Assembly is infrastructure, not a fourth user module.

Modules communicate using normal shader-group sockets: coordinates in mm,
color, metallic, roughness, height in mm, anisotropy, tangent, and scalar masks.
The shader assembly supplies the final Shader output. Material instances share
the same group library but retain independent input values.

Manufacturing coatings are not implemented. Using Principled's optical coat
input to approximate lubricant sheen is allowed within the oil imperfection;
it does not add coating coverage, thickness removal, or substrate reveal.

## Presets and controls

- Metals: Steel, Aluminum, Bronze, Copper, Custom.
- Finishes: Polished, Brushed, Cast, Stonewashed, Machined, Custom.
- Texture sizes: Fine, Medium, Coarse, Custom.
- Wear: None, Light, Moderate, Heavy, Custom.
- Dust, oil and scratches: independent toggles and amounts.
- Custom is live routing, not an operation that writes values into other inputs.
  Manual custom settings survive switching to presets and back.
- Direction, seeds, physical scale, and debug views remain explicit controls.

One generated oil mask is reused from the existing project and stored locally.
It adds useful irregular wipe detail. The rest is procedural. The mask is packed
into the blend and documented in textures/SOURCE.md. Additional maps were avoided.

## Blender 5.2 implementation findings

Native NodeSocketMenu sockets and GeometryNodeMenuSwitch work in ShaderNodeTree
in the installed Blender 5.2.1 LTS. Their internal type names still include
GeometryNode. Menus can pass through the master group into module groups.

Each menu socket is linked to one defining Menu Switch to avoid conflicting enum
definitions. Finish selects an integer once, then scalar comparisons route its
coordinated channels. GeometryNodeIndexSwitch was rejected by this installed
shader tree, so it is not used. This scalar routing is functionally tested; it
does not promise that all unused finish texture branches are skipped at render
time. Custom settings are not guaranteed to automatically hide in the interface.

Reference: [Blender Menu Switch documentation](https://docs.blender.org/manual/sr/5.2/render/shader_nodes/utilities/menu_switch.html).

The gallery Boolean operation introduced an empty material slot during initial
testing. The generator now clears that slot and assigns every face explicitly;
the integration test checks that all gallery faces have materials.

## Validation approach

Use the local Blender binary rather than assume API compatibility from node names.
Render preset outputs to floating-point EXRs to check metal colors and finish
roughness, check saved custom settings, exercise texture-size menus, verify
disabled masks are zero and enabled oil/dust respond, and test packed-image
loading without access to the original script location. Render both the Cycles
and Eevee galleries. `validation.json` records the checks for the delivered build.

## Future development plan — deliberately not implemented

1. Optional manufacturing coating module: paint, phosphate, plating and clearcoat
   as distinct treatments, with their own finish and coverage.
2. Coating damage and substrate reveal: wear removes treatment and exposes the
   correct base material; retain separate finish normals for each surface.
3. External painted/baked mask inputs, including a view-independent alternative
   to screen-space AO in Eevee.
4. Reorderable imperfections and interactions such as oily dust, packed dirt,
   corrosion, oxidation and material-specific patina.
5. Cylindrical/radial mappings, better tangent handling for arbitrary tool paths,
   and optional UV-specific detail assets.
6. A dedicated Material Properties panel only if the native group interface becomes
   cumbersome; no add-on requirement in v1.
7. Measured optical presets, broader alloy coverage, and shader performance tuning.
