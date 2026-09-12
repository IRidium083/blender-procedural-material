# Text and markings module — planning

Status: placeholder and design notes only. No shader, script, or scene yet.

## Goal

Reusable labels, serial numbers, lettering, and logos on existing materials.
Start with Unified Metal, but keep the marking mask usable on wood and plastic.

## Proposed implementation

1. Use a black-and-white or alpha image as the lettering mask. White means
   marking, black means underlying surface. Keep color separate from the mask.
2. Place the image with a dedicated UV map for predictable face placement.
   Offer planar projection later, with a face/region mask to prevent lettering
   appearing on opposite faces. Do not reuse repeating finish coordinates.
3. Expose placement, rotation, size, opacity, marking color, and roughness.
   Use a bounded image region so the lettering appears once; preserve its aspect ratio.
4. Output the coverage mask first, then use it to blend surface properties or
   shaders. Preserve the underlying finish outside the letters.
5. Add optional fading from a supplied wear mask, with a separate marking-wear
   strength. Let users choose whether markings sit beneath or above contamination.

## Appearance modes

| Mode | Suggested behavior |
| --- | --- |
| Printed ink | Blend in a nonmetallic colored surface, with separate roughness |
| Laser marked | Subtle color and roughness change; default to no relief |
| Engraved | Optional shallow negative bump; geometry for deep cuts or silhouettes |
| Raised lettering | Separate Text geometry when actual thickness matters |

For frequently changing wording, use a Blender Text object as the authoring
source. A future Python helper could update the string and render/bake a mask.
Ordinary shader nodes do not provide a general font/string rasterizer. Keep
editable text generation separate from material evaluation; OSL is unnecessary
for the first version.

## Integration and checks

- Initial order: base finish → markings → shared wear/contamination. Keep a
  future placement option for fresh lettering applied over an already worn finish.
- Separate marking coverage from the base metal's wear mask and metallic value.
- Use physical text size where practical, and document UV/projection assumptions.
- Pack mask images into delivered scenes and retain external source files.
- Test crisp text at close range, small text at render distance, rotated placement,
  opposite-face isolation, disabled markings, and Cycles/Eevee appearance.

First milestone: one printed label on a flat sample with editable mask, placement,
color, roughness, and opacity. Add laser marking and engraving after that works.
