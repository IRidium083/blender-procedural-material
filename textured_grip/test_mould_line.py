"""Render-test the actual shader seam mask. Run with -b textured_grip.blend.
Does not save or modify the delivered blend file.
"""
from pathlib import Path
import tempfile
import bpy

scene = bpy.data.scenes.new("Mould Mask Verification")
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=0.004)
plane = bpy.context.object
mat = bpy.data.materials["Textured Grip - Hard Rubber"].copy()
group_node = next(n for n in mat.node_tree.nodes if n.type == "GROUP")
group_node.node_tree = group_node.node_tree.copy()
g = group_node.node_tree
emission = g.nodes.new("ShaderNodeEmission")
g.links.new(g.nodes["Optional Mould Mask"].outputs[0], emission.inputs["Color"])
g.links.new(emission.outputs[0], next(n for n in g.nodes if n.type == "GROUP_OUTPUT").inputs["Shader"])
plane.data.materials.append(mat)
cam = bpy.data.objects.new("Mask Camera", bpy.data.cameras.new("Mask Camera"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, 0, 0.01)
cam.data.type, cam.data.ortho_scale, cam.data.clip_start = "ORTHO", 0.004, 0.0001
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x, scene.render.resolution_y = 128, 32
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "OPEN_EXR"
scene.render.image_settings.color_depth = "32"


def measure():
    with tempfile.TemporaryDirectory(prefix="mould_mask_") as folder:
        scene.render.filepath = str(Path(folder) / "mask.exr")
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = list(image.pixels)[::4]
        bpy.data.images.remove(image)
    weight = sum(pixels)
    center = sum((i % 128) * value for i, value in enumerate(pixels)) / max(weight, 1e-9)
    return weight, center


group_node.inputs["Mould Line"].default_value = False
assert measure()[0] < 1e-6, "Disabled seam must be zero"
group_node.inputs["Mould Line"].default_value = True
weight, center = measure()
assert weight > 1 and abs(center - 63.5) < 1, (weight, center)
group_node.inputs["Mould Offset"].default_value = 0.001
shifted_weight, shifted_center = measure()
assert shifted_center > center + 25, "Offset must move the rendered seam"
group_node.inputs["Mould Offset"].default_value = 0
group_node.inputs["Mould Width"].default_value *= 2
assert measure()[0] > weight * 1.7, "Width must widen the rendered seam"
assert bpy.data.images["Molded Grip Height"].packed_file
print("PASS: disabled, centered, offset, width, and packed-image checks")
