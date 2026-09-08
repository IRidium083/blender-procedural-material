"""Render a recessed sample in both engines to inspect edge wear and dust.
Run: blender -b test.blend --python-exit-code 1 -P test_material.py
"""
from pathlib import Path
import sys
import bpy

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import worn_painted_metal as material_script

cube = bpy.data.objects["Cube"]
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, -0.9, 0.15))
cutter = bpy.context.object
cutter.scale = (0.66, 0.5, 0.58)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.context.view_layer.objects.active = cube
modifier = cube.modifiers.new("Recess for Dust Test", "BOOLEAN")
modifier.operation = "DIFFERENCE"
modifier.object = cutter
bpy.ops.object.modifier_apply(modifier=modifier.name)
bpy.data.objects.remove(cutter, do_unlink=True)
material = material_script.make_material()
cube.data.materials.clear()
cube.data.materials.append(material)
bpy.ops.object.select_all(action="DESELECT")
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
scene = bpy.context.scene
material_script.preview(scene, cube, DIRECTORY, False)
group = next(n.node_tree for n in material.node_tree.nodes if n.type == "GROUP")
assert all(n.inputs["Distance"].is_linked for n in group.nodes if n.type == "AMBIENT_OCCLUSION")
assert len([n for n in group.nodes if n.type == "AMBIENT_OCCLUSION"]) == 2
assert group.nodes["Dust Is Nonmetallic"].outputs[0].is_linked
for engine, suffix in [("CYCLES", "cycles"), ("CYCLES", "clean"), ("BLENDER_EEVEE", "eevee")]:
    scene.render.engine = engine
    instance = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    instance.inputs["Edge Wear"].default_value = 0 if suffix == "clean" else 0.85
    instance.inputs["Dust Amount"].default_value = 0 if suffix == "clean" else 0.8
    scene.render.filepath = str(DIRECTORY / f"recessed_metal_{suffix}.png")
    bpy.ops.render.render(write_still=True)
scene.render.engine = "CYCLES"
scene.render.filepath = str(DIRECTORY / "recessed_metal_cycles.png")
bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY / "worn_painted_metal.blend"))
print("PASS: Cycles and Eevee renders; recessed geometry; edge and dust disabled comparison")
