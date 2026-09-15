"""Render-backed spacing, unit conversion, veneer and renderer checks.
Run: Blender -b wood.blend --python-exit-code 1 -P test_material.py
"""
import json
import math
from pathlib import Path
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
shared_finish = next(g for g in bpy.data.node_groups if g.get('surface_marks_version') == 1)
scratch_image = shared_finish.nodes['Shared Scratch Image'].image
assert scratch_image.packed_file and len(scratch_image.pixels) > 0
assert scratch_image.colorspace_settings.name == 'Non-Color'
assert shared_finish.nodes['Scratch Coverage'].inputs[0].links[0].from_node.type == 'TEX_IMAGE'

master = bpy.data.materials['Custom Wood'].node_tree.nodes['Wood Controls'].node_tree
simple_inputs = ['Color Tint','Grain Scale','Grain Direction','Grain Detail','Finish','Surface Wear','Dust']
materials = [name+' Wood' for name in ('Pine','Maple','Oak','Walnut','Ebony')]+['Plywood Face','Plywood Edge']
for name in materials:
    material = bpy.data.materials[name]
    wrapper = material.node_tree.nodes['Wood Controls'].node_tree
    inputs = [s.name for s in wrapper.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT']
    assert inputs == simple_inputs+(['Ply Thickness mm'] if name == 'Plywood Edge' else []), (name,inputs)
    assert wrapper.nodes['Advanced Wood Settings'].node_tree == master
    assert material.use_fake_user and not material.asset_data
assert bpy.data.materials['Custom Wood'].use_fake_user
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
group.inputs['Wood Preset'].default_value = 'Custom'
group.inputs['Distortion mm'].default_value = 0
group.inputs['Ring Center Offset mm'].default_value = (0, 0, 0)
coordinates = group.node_tree.nodes['Coordinates mm']
controls = group
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
    controls.inputs['Scene Unit m'].default_value = units
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
# Clear finish is layered over wood; imperfections are independent controls.
shared = master.nodes['Shared Surface Finish'].node_tree
assert master.nodes['Sanded Wood'].inputs['Coat Normal'].links[0].from_node.name == 'Shared Surface Finish'
assert master.nodes['Shared Surface Deposits'].inputs['Surface'].links[0].from_node.name == 'Sanded Wood'
assert shared.nodes['Scratches in Top Finish'].inputs['Normal'].links[0].from_node.name == 'Uncoated Geometry'
group.inputs['Surface Scratches'].default_value = 0
group.inputs['Smudges'].default_value = 0
group.inputs['Surface Dust'].default_value = 0
group.inputs['Clear Finish'].default_value = 'Clear Paint'
sample('Clear paint coat weight', 'Coat Weight', (0,0,0), expected=0.85)
sample('Clear paint clean roughness', 'Coat Roughness', (0,0,0), expected=0.16)
group.inputs['Clear Finish'].default_value = 'Wax'
sample('Wax softer reflection weight', 'Coat Weight', (0,0,0), expected=0.85*0.65)
sample('Wax clean roughness', 'Coat Roughness', (0,0,0), expected=0.38)
group.inputs['Clear Finish'].default_value = 'None'
sample('Finish disabled', 'Coat Weight', (0,0,0), expected=0)
for channel in ('Scratch Mask','Smudge Mask','Dust Mask'):
    sample('Disabled '+channel, channel, (12,13,4), expected=0)
group.inputs['Clear Finish'].default_value = 'Clear Paint'
group.inputs['Smudges'].default_value = 1
smudged = sample('Smudges alter top coat', 'Coat Roughness', (12,13,4))
assert smudged > 0.16
# Presets route appearance without mutating the stored custom settings.
group.inputs['Pore Size mm'].default_value = 0.18
group.inputs['Ring Contrast'].default_value = 0.42
for name,size,contrast,red in [
    ('Pine',0.04,1,0.48), ('Maple',0.06,0.3,0.57),
    ('Oak',0.25,0.65,0.38), ('Walnut',0.14,0.55,0.16), ('Ebony',0.055,0.35,0.018),
]:
    group.inputs['Wood Preset'].default_value = name
    sample(name+' pore size','Resolved Pore Size mm',(0,0,0),expected=size)
    sample(name+' ring contrast','Resolved Ring Contrast',(0,0,0),expected=contrast)
    sample(name+' light color red','Resolved Light Color',(0,0,0),expected=red)
    assert abs(group.inputs['Pore Size mm'].default_value-0.18) < 0.00001
    assert abs(group.inputs['Ring Contrast'].default_value-0.42) < 0.00001
group.inputs['Wood Preset'].default_value = 'Custom'
sample('Custom pore size restored','Resolved Pore Size mm',(0,0,0),expected=0.18)
sample('Custom contrast restored','Resolved Ring Contrast',(0,0,0),expected=0.42)
group.inputs['Vessel Pore Strength'].default_value = 0
sample('Custom vessel pores disabled','Pore Mask',(0,0,0),expected=0)

# Exercise the actual public wrappers through the renderer. Diagnostic sockets
# are added only to temporary copies; delivered materials expose Shader alone.
def use_wrapper(name):
    global controls, coordinates
    source = bpy.data.materials[name].node_tree.nodes['Wood Controls']
    group.node_tree = source.node_tree.copy()
    for socket in source.inputs:
        group.inputs[socket.name].default_value = socket.default_value
    controls = group.node_tree.nodes['Advanced Wood Settings']
    controls.node_tree = master.copy()
    coordinates = controls.node_tree.nodes['Coordinates mm']
    for link in list(coordinates.inputs[0].links):
        controls.node_tree.links.remove(link)
    for socket in master.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'OUTPUT' and socket.name != 'Shader':
            group.node_tree.interface.new_socket(name=socket.name,in_out='OUTPUT',socket_type=socket.socket_type)
            group.node_tree.links.new(controls.outputs[socket.name],group.node_tree.nodes['Outputs'].inputs[socket.name])

for species, red in [('Pine',.48),('Maple',.57),('Oak',.38),('Walnut',.16),('Ebony',.018)]:
    use_wrapper(species+' Wood')
    sample(species+' simplified palette','Resolved Light Color',(0,0,0),expected=red)
    expected_weight = .75*.65 if species == 'Maple' else .85
    sample(species+' simplified finish','Coat Weight',(0,0,0),expected=expected_weight)

use_wrapper('Oak Wood')
base = sample('Oak untinted','Base Color',(12,13,4))
group.inputs['Color Tint'].default_value = (.5,.5,.5,1)
tinted = sample('Oak half tint','Base Color',(12,13,4))
assert abs(tinted-base*.5) < .0001
group.inputs['Grain Detail'].default_value = 0
sample('Simplified detail zero removes relief','Resolved Relief mm',(12,13,4),expected=0)
sample('Simplified detail zero removes vessel color','Pore Mask',(12,13,4),expected=0)
group.inputs['Grain Detail'].default_value = 2
sample('Simplified detail increases relief','Resolved Relief mm',(12,13,4),expected=.044)
group.inputs['Surface Wear'].default_value = 0
group.inputs['Dust'].default_value = 0
for channel in ('Scratch Mask','Smudge Mask','Dust Mask'):
    sample('Simplified clean '+channel,channel,(12,13,4),expected=0)
group.inputs['Surface Wear'].default_value = 1
assert sample('Combined wear enables handling marks','Smudge Mask',(12,13,4)) > .01
group.inputs['Dust'].default_value = 1
assert sample('Independent dust enabled','Dust Mask',(12,13,4)) > .01
group.inputs['Finish'].default_value = 'None'
sample('Simplified raw finish','Coat Weight',(0,0,0),expected=0)
group.inputs['Finish'].default_value = 'Wax'
sample('Simplified wax finish','Coat Weight',(0,0,0),expected=.85*.65)

use_wrapper('Plywood Edge')
controls.inputs['Distortion mm'].default_value = 0
controls.inputs['Ring Center Offset mm'].default_value = (0,0,0)
group.inputs['Grain Scale'].default_value = 2
sample('Grain Scale doubles ring period','Ring Pattern',(0,1.25,0),expected=1)
sample('Grain Scale preserves physical ply centers','Layer Tone',(0,0,.75),expected=1)
sample('Grain Scale preserves glue boundaries','Glue Mask',(0,0,1.5),expected=1)
group.inputs['Ply Thickness mm'].default_value = 2
sample('Public ply thickness moves glue boundary','Glue Mask',(0,0,2),expected=1)
sample('Public ply thickness moves ply center','Layer Tone',(0,0,3),expected=0)
group.inputs['Grain Direction'].default_value = (0,0,math.pi/2)
sample('Public grain direction rotates pattern','Ring Pattern',(1.25,0,0),expected=1)
sample('Simplified centimeter scene conversion','Ring Pattern',(1.25,0,0),units=.01,expected=1)

bpy.context.window.scene = gallery
gallery.render.engine = 'BLENDER_EEVEE'
gallery.render.filepath = str(DIRECTORY/'wood_eevee.png')
bpy.ops.render.render(write_still=True)
(DIRECTORY/'validation.json').write_text(json.dumps({'passed': True, 'checks': checks,
    'geometry': '240mm boards; 18mm plywood; explicit veneer faces',
    'public_inputs': {'solid_wood_and_plywood_face': simple_inputs,'plywood_edge_extra': 'Ply Thickness mm'},
    'materials': materials+['Custom Wood'],
    'renderers': ['Cycles', 'Eevee']}, indent=2), encoding='utf-8')
print('PASS: simplified interfaces, control response, species presets, physical scale, coatings and Eevee gallery')
