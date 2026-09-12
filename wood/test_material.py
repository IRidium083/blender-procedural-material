"""Render-backed spacing, unit conversion, veneer and renderer checks.
Run: Blender -b wood.blend --python-exit-code 1 -P test_material.py
"""
import json
from pathlib import Path
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
master = bpy.data.materials['Procedural Wood'].node_tree.nodes['Wood Controls'].node_tree
assert not any(n.type == 'TEX_IMAGE' for n in master.nodes)
assert len([n for n in master.nodes if n.type == 'TEX_WAVE']) == 3
panel = bpy.data.objects['Plywood 18mm']
assert abs(panel.dimensions.z - 0.018) < 0.00001
for face in panel.data.polygons:
    assert face.material_index == (1 if abs(face.normal.z) > 0.5 else 0)
for obj in gallery.objects:
    if obj.type == 'MESH':
        assert tuple(obj.scale) == (1, 1, 1)
        assert all(obj.data.materials[p.material_index] for p in obj.data.polygons)

scene = bpy.data.scenes.new('Wood Numeric Checks')
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=2)
plane = bpy.context.object
mat = bpy.data.materials.new('Wood Test')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
emission = mat.node_tree.nodes.new('ShaderNodeEmission')
mat.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
group = mat.node_tree.nodes.new('ShaderNodeGroup')
group.node_tree = master.copy()
group.inputs['Distortion mm'].default_value = 0
group.inputs['Ring Center Offset mm'].default_value = (0, 0, 0)
coordinates = group.node_tree.nodes['Coordinates mm']
for link in list(coordinates.inputs[0].links):
    group.node_tree.links.remove(link)
cam = bpy.data.objects.new('Test Camera', bpy.data.cameras.new('Test Camera'))
scene.collection.objects.link(cam)
cam.location = (0, 0, 1)
cam.data.type, cam.data.ortho_scale = 'ORTHO', 1
scene.camera = cam
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 8
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
checks = []


def sample(label, channel, point_mm, units=1, expected=None):
    group.inputs['Scene Unit m'].default_value = units
    coordinates.inputs[0].default_value = tuple(p/(units*1000) for p in point_mm)
    mat.node_tree.links.new(group.outputs[channel], emission.inputs['Color'])
    with tempfile.TemporaryDirectory(prefix='wood_check_') as folder:
        scene.render.filepath = str(Path(folder)/'value.exr')
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = list(image.pixels)
        value = sum(pixels[0::4])/(len(pixels)//4)
        bpy.data.images.remove(image)
    checks.append({'check': label, 'value': value})
    if expected is not None:
        assert abs(value-expected) < 0.015, (label, value, expected)
    return value


sample('Ring quarter period 0.625mm', 'Ring Pattern', (0, 0.625, 0), expected=1)
sample('Ring three-quarter period 1.875mm', 'Ring Pattern', (0, 1.875, 0), expected=0)
sample('Ring repeat 3.125mm', 'Ring Pattern', (0, 3.125, 0), expected=1)
sample('Centimeter scene units preserve ring spacing', 'Ring Pattern', (0, 0.625, 0), units=0.01, expected=1)
sample('First ply center', 'Layer Tone', (0, 0, 0.75), expected=1)
sample('Second ply center', 'Layer Tone', (0, 0, 2.25), expected=0)
sample('Third ply center', 'Layer Tone', (0, 0, 3.75), expected=1)
sample('Glue boundary', 'Glue Mask', (0, 0, 1.5), expected=1)
sample('Inside ply no glue', 'Glue Mask', (0, 0, 0.75), expected=0)
group.inputs['Glue Width mm'].default_value = 0
sample('Glue disabled', 'Glue Mask', (0, 0, 1.5), expected=0)
bpy.context.window.scene = gallery
gallery.render.engine = 'BLENDER_EEVEE'
gallery.render.filepath = str(DIRECTORY/'wood_eevee.png')
bpy.ops.render.render(write_still=True)
(DIRECTORY/'validation.json').write_text(json.dumps({'passed': True, 'checks': checks,
    'geometry': '240mm boards; 18mm plywood; explicit veneer faces',
    'renderers': ['Cycles', 'Eevee']}, indent=2), encoding='utf-8')
print('PASS: physical ring/ply spacing, unit conversion, glue masks, face assignment, Eevee gallery')
