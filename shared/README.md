# Shared material modules

`surface_finish.py` builds **Shared - Clear Finish and Surface Imperfections v2**.
Wood and fiberglass reinforced plastic both use this ordinary shader node group.
The shared group is cached by name and version within each Blender file.

The module takes millimeter coordinates, scene-unit conversion, finish selection,
and independent scratch/smudge/dust controls. It outputs coat weight, roughness,
normal, and three diagnostic masks. It knows nothing about wood grain or fibers.

`attach_finish(graph, principled, coordinates_mm, scene_units, defaults=None)`
adds group controls and connects the coat channels to an existing Principled
shader. It returns a shader output with nonmetallic dust above the coated surface.
The adapter expects `node`, `input`, `output`, `set`, and `tree` on the graph builder.
FRP overrides the default imperfection strengths to zero; wood enables light wear.

Layer order:

```text
Substrate color / roughness / normal
    → Principled clear coat (paint or wax approximation)
      with image scratches and procedural smudges
    → separate dust shader mixed over the finished surface
```

The scratch image is Non-Color and packed in generated scenes. Only its mask is
image-based; smudges and upward-biased dust remain procedural. Scratch Tile mm
scales the entire image; it cannot independently resize stroke width and length.
See [texture source and prompt](textures/SOURCE.md).

To modify the shared builder, regenerate the consuming scenes. Increment the
group version when its implementation or interface changes, so an existing
cached group is not silently reused. Appended groups render without Python.
Both material generators embed a copy of the shared source for regeneration
when the project files are unavailable and the scratch image remains packed.

Coat Amount is an optical weight, not physical film thickness. Clear Finish=None
removes coat effects but leaves dust independently controlled. Smudges and scratches
modify the coat only; this module does not remove coating or expose a substrate.
