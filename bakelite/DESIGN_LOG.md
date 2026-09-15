# Bakelite reference interpretation and build log

## Supplied references

- [type1 ref1.png](<references/type1 ref1.png>): dark resin with irregular amber fragment clusters and short,
  direction-changing streaks.
- [type1 ref2.png](<references/type1 ref2.png>): brighter orange/amber example with finer mottling.
- [type1 ref3.png](<references/type1 ref3.png>): curved dark surfaces with larger interrupted filler packets
  and variable surface gloss.
- [type2 ref1.png](<references/type2 ref1.png>): golden-brown resin with fine long curved flow lines.
- [type2 ref2.png](<references/type2 ref2.png>): darker brown resin with higher-contrast amber flow streaks.

These describe visible appearance only; the precise resin/filler chemistry and
physical pattern dimensions cannot be established from the photographs. The
original user-supplied images are preserved and are not used as material textures.

## Implementation steps

1. Inspect all five references. Separate the two pattern families by construction:
   randomly oriented short filler packets versus continuous directional flow.
   Create two material groups, not a pattern dropdown. Offer two palettes each.
2. Use object coordinates converted to physical millimeters, then apply pattern
   scale, direction and seed. Keep resin-skin microtexture at a fixed physical
   size independent of pattern scale. Preview on 200 mm panels and curved forms.
3. For Type 1, distort a 3D Voronoi field, rotate strand coordinates using each
   region's random color, and combine stretched noise with resin pools and fine
   specks. Region boundaries intentionally break the strand directions.
4. For Type 2, distort coordinates with broad smooth noise and sample two scales
   of elongated noise. Narrow the threshold to fine lines. Reduce through-depth
   variation so front-surface flow stays elongated instead of turning into dots.
5. Share the final molded-resin shading through shared/resin_finish.py. Feed the
   patterns into color only. Add fine skin bump and uneven roughness independently,
   with a modest smooth coat reflection and no metal or transmission.
6. Render and compare the first procedural attempt. Refine overly thick Type 2
   bands, reduce Type 1 fine speck coverage, and reposition studio lights so broad
   reflections do not obscure the dark resin. Keep all patterns procedural.
7. Render gallery/detail previews in Cycles and validate with emission EXRs for
   masks, color, controls and scene-unit equivalence. Render an Eevee gallery.
   Check all reachable material groups contain zero image-texture nodes.
8. Save bakelite.blend with both sources embedded, ordinary appendable material
   datablocks and fake users. Document controls and remaining approximation limits.

## Image-texture decision

No image texture was needed for this procedural first pass. The patterns reproduce
the distinction between fragment-rich and flowing resin appearances. Exact shaped
filler flakes and photograph-specific flow would need further art direction or a
pattern mask; introduce one only if that becomes necessary after review.
