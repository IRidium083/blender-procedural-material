"""Validate and render the saved aluminum scene in Eevee.
Run with Blender -b machined_aluminum.blend --python-exit-code 1 -P test_material.py.
"""
from pathlib import Path
import bpy

material = bpy.data.materials["Machined Aluminum"]
group = next(n.node_tree for n in material.node_tree.nodes if n.type == "GROUP")
shader = group.nodes["Solid Machined Aluminum"]
assert shader.inputs["Metallic"].default_value == 1
assert shader.inputs["Tangent"].is_linked
assert shader.inputs["Roughness"].is_linked
assert shader.inputs["Normal"].is_linked
assert not any(n.type == "TEX_IMAGE" for n in group.nodes)
assert group.nodes["Shallow Tool Grooves"].inputs["Distance"].is_linked
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.filepath = str(Path(__file__).resolve().parent / "machined_aluminum_eevee.png")
bpy.ops.render.render(write_still=True)
print("PASS: aluminum metal, directional tangent, procedural roughness and grooves; Eevee render")
