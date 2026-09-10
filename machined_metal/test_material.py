"""Validate and render the saved machined metal scene in Eevee.
Run with Blender -b machined_metal.blend --python-exit-code 1 -P test_material.py.
"""
from pathlib import Path
import bpy

material = bpy.data.materials["Machined Metal"]
group = next(n.node_tree for n in material.node_tree.nodes if n.type == "GROUP")
shader = group.nodes["Solid Machined Metal"]
assert shader.inputs["Metallic"].default_value == 1
assert shader.inputs["Tangent"].is_linked
assert shader.inputs["Roughness"].is_linked
assert not shader.inputs["Normal"].is_linked
assert not any(n.type in {"BUMP", "NORMAL_MAP", "DISPLACEMENT"} for n in group.nodes)
assert shader.inputs["Base Color"].links[0].from_node == group.nodes["Subtle Machining Color"]
assert shader.inputs["Anisotropic"].links[0].from_node == group.nodes["Varied Anisotropy"]
assert group.nodes["Subtle Machining Color"].inputs[2].links[0].from_node.type == "TEX_IMAGE"
assert group.nodes["Machining Anisotropy Variation"].inputs[0].links[0].from_node == group.nodes["Center Finish Noise"]
assert not any(s.name == "Tool Mark Depth" for s in group.interface.items_tree)
images = [n.image for n in group.nodes if n.type == "TEX_IMAGE"]
# Pixel access loads packed image buffers lazily after opening a blend file.
assert images and all(image.packed_file and len(image.pixels) > 0 for image in images)
assert all(image.colorspace_settings.name == "Non-Color" for image in images)
assert "Machined Aluminum" not in bpy.data.materials
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.filepath = str(Path(__file__).resolve().parent / "machined_metal_eevee.png")
bpy.ops.render.render(write_still=True)
print("PASS: machined metal, directional tangent, image-driven color, anisotropy and roughness; no normal perturbation; Eevee render")
