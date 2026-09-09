"""Render a recessed sample in both engines to inspect edge wear and dust.
Run: blender -b worn_painted_metal.blend --python-exit-code 1 -P test_material.py
"""
from pathlib import Path
import sys
import bpy

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import worn_painted_metal as material_script

scene = bpy.context.scene
existing_scene = Path(bpy.data.filepath).name == "worn_painted_metal.blend"
if existing_scene:
    # Rebuild the shared material without altering scene geometry or lighting.
    material = material_script.make_material()
    assert any(material == slot.material for obj in scene.objects
               if obj.type == "MESH" for slot in obj.material_slots), "Material is not assigned"
else:
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
assert not any("scratch" in n.name.lower() for n in group.nodes)
assert not any("Scratch" in item.name for item in group.interface.items_tree)
for name in ("Edge Only Exposed Steel", "Edge Only Rust Border"):
    mask = group.nodes[name]
    assert mask.operation == "MULTIPLY"
    assert mask.inputs[1].links[0].from_node == group.nodes["Edge Wear Amount"]
assert group.nodes["Paint / Steel Roughness"].inputs[1].links[0].from_node == group.nodes["Varied Paint Roughness"]
instance = next(n for n in material.node_tree.nodes if n.type == "GROUP")
original_edge = instance.inputs["Edge Wear"].default_value
original_dust = instance.inputs["Dust Amount"].default_value
for engine, suffix in [("CYCLES", "cycles"), ("CYCLES", "clean"), ("BLENDER_EEVEE", "eevee")]:
    scene.render.engine = engine
    instance = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    instance.inputs["Edge Wear"].default_value = 0 if suffix == "clean" else original_edge
    instance.inputs["Dust Amount"].default_value = 0 if suffix == "clean" else original_dust
    scene.render.filepath = str(DIRECTORY / f"recessed_metal_{suffix}.png")
    bpy.ops.render.render(write_still=True)
instance.inputs["Edge Wear"].default_value = original_edge
instance.inputs["Dust Amount"].default_value = original_dust
# Keep the embedded source in sync when the scene includes the script.
for block in bpy.data.texts:
    if block.name == "worn_painted_metal.py":
        block.clear()
        block.write((DIRECTORY / "worn_painted_metal.py").read_text(encoding="utf-8"))
        block.filepath = str(DIRECTORY / "worn_painted_metal.py")
scene.render.engine = "CYCLES"
scene.render.filepath = str(DIRECTORY / "recessed_metal_cycles.png")
bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY / "worn_painted_metal.blend"))
print("PASS: Cycles and Eevee renders; recessed geometry; edge and dust disabled comparison")
