"""Integration checks: menu evaluation, custom preservation, masks, packed data.
Run against unified_metal.blend. --render-eevee also writes an Eevee gallery.
"""
import json
from pathlib import Path
import sys
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
embedded = bpy.data.texts["unified_metal.py"].as_string()
namespace = {"__name__": "verify", "__file__": "C:/missing/unified_metal.py"}
exec(embedded, namespace)
image = bpy.data.images[namespace["IMAGE_NAME"]]
assert image.packed_file and image.colorspace_settings.name == "Non-Color"
assert namespace["oil_image"]() == image
master = next(m.node_tree.nodes["Unified Metal"].node_tree for m in bpy.data.materials
              if m.get("um_version") == "1.0")
modules = {n.node_tree.name: n.node_tree for n in master.nodes if n.type == "GROUP"}
assert len(modules) == 3
all_images = [n for g in modules.values() for n in g.nodes if n.type == "TEX_IMAGE"]
assert len(all_images) == 1 and all_images[0].image == image
for obj in gallery.objects:
    if obj.type == "MESH":
        assert all(obj.data.materials[p.material_index] is not None for p in obj.data.polygons), obj.name

scene = bpy.data.scenes.new("UM Verification")
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=0.02)
plane = bpy.context.object
mat = bpy.data.materials.new("UM Verification Material")
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
emission = mat.node_tree.nodes.new("ShaderNodeEmission")
mat.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
test_node = mat.node_tree.nodes.new("ShaderNodeGroup")
coords = mat.node_tree.nodes.new("ShaderNodeTexCoord")
scale = mat.node_tree.nodes.new("ShaderNodeVectorMath")
scale.operation = "SCALE"
scale.inputs["Scale"].default_value = 1000
mat.node_tree.links.new(coords.outputs["Object"], scale.inputs[0])
cam = bpy.data.objects.new("Verification Camera", bpy.data.cameras.new("Verification Camera"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, 0, 0.1)
cam.data.type, cam.data.ortho_scale, cam.data.clip_start = "ORTHO", 0.01, 0.001
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 16
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "OPEN_EXR"
scene.render.image_settings.color_depth = "32"
checks = []


def module(name, channel):
    test_node.node_tree = modules["UM v1 | " + name]
    mat.node_tree.links.new(test_node.outputs[channel], emission.inputs["Color"])
    if "Coordinates mm" in test_node.inputs:
        mat.node_tree.links.new(scale.outputs[0], test_node.inputs["Coordinates mm"])


def evaluate(label):
    with tempfile.TemporaryDirectory(prefix="um_check_") as folder:
        scene.render.filepath = str(Path(folder) / "value.exr")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = list(img.pixels)
        rgb = [sum(pixels[c::4]) / (len(pixels) // 4) for c in range(3)]
        bpy.data.images.remove(img)
    checks.append({"check": label, "mean_rgb": rgb})
    return rgb


module("1 Base Metal", "Color")
for metal, expected in [("Steel", (0.55, 0.58, 0.6)), ("Aluminum", (0.83, 0.85, 0.88)),
                         ("Bronze", (0.55, 0.32, 0.12)), ("Copper", (0.9, 0.47, 0.28))]:
    test_node.inputs["Base Metal"].default_value = metal
    got = evaluate("Base " + metal)
    assert max(abs(a-b) for a, b in zip(got, expected)) < 0.01, (metal, got)
test_node.inputs["Custom Metal Color"].default_value = (0.2, 0.3, 0.4, 1)
test_node.inputs["Base Metal"].default_value = "Custom"
assert max(abs(a-b) for a,b in zip(evaluate("Custom metal"), (0.2, 0.3, 0.4))) < 0.01
test_node.inputs["Base Metal"].default_value = "Steel"
evaluate("Preset after custom")
assert abs(test_node.inputs["Custom Metal Color"].default_value[0] - 0.2) < 1e-6

module("2 Surface Finish", "Roughness")
test_node.inputs["Texture Size"].default_value = "Medium"
test_node.inputs["Custom Roughness"].default_value = 0.37
for finish, expected in [("Polished", 0.12), ("Brushed", 0.32), ("Cast", 0.68),
                          ("Stonewashed", 0.48), ("Machined", 0.22), ("Custom", 0.37)]:
    test_node.inputs["Finish"].default_value = finish
    value = evaluate("Finish " + finish)[0]
    assert abs(value - expected) < 0.055, (finish, value)
assert abs(test_node.inputs["Custom Roughness"].default_value - 0.37) < 1e-6
test_node.inputs["Finish"].default_value = "Cast"
for size in ["Fine", "Medium", "Coarse", "Custom"]:
    test_node.inputs["Texture Size"].default_value = size
    assert 0.62 < evaluate("Size " + size)[0] < 0.74

module("3 Imperfections", "Oil Mask")
for name, value in {"Wear Level": "None", "Scratches": False, "Dust": False, "Oil": False}.items():
    test_node.inputs[name].default_value = value
for channel in ["Oil Mask", "Dust Mask", "Scratch Mask", "Wear Mask"]:
    mat.node_tree.links.new(test_node.outputs[channel], emission.inputs["Color"])
    assert max(evaluate("Disabled " + channel)) < 1e-6
test_node.inputs["Oil"].default_value = True
test_node.inputs["Oil Patch mm"].default_value = 4
mat.node_tree.links.new(test_node.outputs["Oil Mask"], emission.inputs["Color"])
assert evaluate("Enabled oil")[0] > 0.01
test_node.inputs["Dust"].default_value = True
mat.node_tree.links.new(test_node.outputs["Dust Mask"], emission.inputs["Color"])
assert evaluate("Enabled upward dust")[0] > 0.01

bpy.context.window.scene = gallery
if "--render-eevee" in sys.argv:
    gallery.render.engine = "BLENDER_EEVEE"
    gallery.render.resolution_percentage = 70
    gallery.render.filepath = str(DIRECTORY / "unified_metal_eevee.png")
    bpy.ops.render.render(write_still=True)
report = {"blender": bpy.app.version_string, "passed": len(checks), "packed_image": True,
          "native_menu_evaluation": True, "checks": checks,
          "eevee_render": "--render-eevee" in sys.argv}
(DIRECTORY / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("PASS", len(checks), "rendered checks; packed image; native presets; custom values preserved")
