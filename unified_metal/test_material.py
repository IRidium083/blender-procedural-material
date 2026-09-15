"""Render-backed checks for separate finish families and shared imperfections.
Run against unified_metal.blend; --render-eevee writes the Eevee gallery.
"""
import json
import math
from pathlib import Path
import sys
import tempfile
import bpy
from mathutils import Euler, Vector

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
namespace = {'__name__':'verify','__file__':'C:/missing/unified_metal.py'}
exec(bpy.data.texts['unified_metal.py'].as_string(),namespace)
assert bpy.data.texts.get('shared_surface_finish.py')
image = namespace['oil_image']()
shared = namespace['shared_surface_group']()
scratch_image = shared.nodes['Shared Scratch Image'].image
for texture in (image,scratch_image):
    assert texture.packed_file and texture.colorspace_settings.name == 'Non-Color'
assert shared.get('surface_marks_version') == 1
families = namespace['FINISHES']
cores,structures,public_inputs = {},{},{}
for family in families:
    material = bpy.data.materials['UM '+family+' Metal']
    assert material.use_fake_user and not material.asset_data
    group = material.node_tree.nodes['Metal Controls'].node_tree
    cores[family] = group if family == 'Custom' else group.nodes['Advanced Metal Settings'].node_tree
    structures[family] = cores[family].nodes['Finish Structure'].node_tree
    public_inputs[family] = [s.name for s in group.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT']
    assert 'Finish' not in public_inputs[family] and 'Texture Size' not in public_inputs[family]
    assert 'Wear Level' not in public_inputs[family]
    assert not any(n.type == 'MENU_SWITCH' for n in structures[family].nodes)
    assert len([n for n in structures[family].nodes if n.type == 'TEX_NOISE']) == 1
    if family != 'Custom':
        assert len(public_inputs[family]) <= 10
        assert ('Direction' in public_inputs[family]) == (family in ('Brushed','Machined'))
        assert 'Scene Unit m' not in public_inputs[family]
assert len(set(structures.values())) == 6
imperfections = cores['Polished'].nodes['Metal Imperfections'].node_tree
assert all(core.nodes['Metal Imperfections'].node_tree == imperfections for core in cores.values())
assert imperfections.nodes['Shared Surface Imperfections'].node_tree == shared
assert not imperfections.nodes.get('Sparse Directional Abrasion')
assert 'Finish Index' not in imperfections.nodes['Shared Surface Imperfections'].inputs
assert all(c.nodes['Shared Surface Deposits'].node_tree.get('surface_deposits_version') == 1 for c in cores.values())
base = cores['Polished'].nodes['Base Metal'].node_tree
assert all(cores[f].nodes['Base Metal'].node_tree == base for f in families if f != 'Custom')
for obj in gallery.objects:
    if obj.type == 'MESH':
        assert all(obj.data.materials[p.material_index] for p in obj.data.polygons)
        assert tuple(obj.scale) == (1,1,1)

scene = bpy.data.scenes.new('UM Verification')
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=.02)
plane = bpy.context.object
mat = bpy.data.materials.new('UM Verification Material')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
emission = mat.node_tree.nodes.new('ShaderNodeEmission')
mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
node = mat.node_tree.nodes.new('ShaderNodeGroup')
coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
scale = mat.node_tree.nodes.new('ShaderNodeVectorMath')
scale.operation = 'SCALE'
scale.inputs['Scale'].default_value = 1000
mat.node_tree.links.new(coords.outputs['Object'],scale.inputs[0])
cam = bpy.data.objects.new('Verification Camera',bpy.data.cameras.new('Verification Camera'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0,0,.1)
cam.data.type,cam.data.ortho_scale,cam.data.clip_start = 'ORTHO',.01,.001
scene.render.engine = 'CYCLES'
scene.cycles.samples,scene.cycles.use_denoising = 4,False
scene.render.resolution_x = scene.render.resolution_y = 24
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
checks = []


def use(tree,channel):
    # Blender can retain links by socket identifier when replacing node_tree.
    for link in list(mat.node_tree.links):
        if link.to_node == node or link.from_node == node:
            mat.node_tree.links.remove(link)
    node.node_tree = tree
    for socket in tree.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT' and socket.socket_type != 'NodeSocketMenu':
            node.inputs[socket.name].default_value = socket.default_value
    if 'Coordinates mm' in node.inputs:
        mat.node_tree.links.new(scale.outputs[0],node.inputs['Coordinates mm'])
    output_channel(channel)


def output_channel(channel):
    mat.node_tree.links.new(node.outputs[channel],emission.inputs['Color'])


def evaluate(label,expected=None,tolerance=.01):
    with tempfile.TemporaryDirectory(prefix='um_check_') as folder:
        scene.render.filepath = str(Path(folder)/'value.exr')
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath,check_existing=False)
        pixels = list(img.pixels)
        rgb = [sum(pixels[c::4])/(len(pixels)//4) for c in range(3)]
        bpy.data.images.remove(img)
    checks.append({'check':label,'mean_rgb':rgb})
    if expected is not None:
        expected = [expected]*3 if isinstance(expected,(float,int)) else expected
        assert max(abs(a-b) for a,b in zip(rgb,expected)) < tolerance,(label,rgb,expected)
    return rgb


use(base,'Color')
for metal,color in [('Steel',(.55,.58,.6)),('Aluminum',(.83,.85,.88)),('Bronze',(.55,.32,.12)),('Copper',(.9,.47,.28))]:
    node.inputs['Base Metal'].default_value = metal
    evaluate('Base '+metal,color)
for family in families:
    use(structures[family],'Roughness')
    evaluate(family+' finish roughness',namespace['FINISH_DEFAULTS'][family][0],.06)
use(structures['Machined'],'Height mm')
evaluate('Machining marks have no height',0,.000001)
node.inputs['Surface Detail'].default_value = 2
evaluate('Strong machining detail still has no height',0,.000001)
output_channel('Color Factor')
assert evaluate('Machining marks modulate color')[0] < .98
output_channel('Anisotropy')
assert 0 < evaluate('Machining anisotropy')[0] < 1
node.inputs['Surface Detail'].default_value = 0
output_channel('Color Factor')
evaluate('Zero machining detail removes color marks',1)
output_channel('Anisotropy')
evaluate('Zero machining detail restores uniform anisotropy',.4)

# Full inverse Euler rotation and object-to-world tangent on a planar surface.
use(structures['Brushed'],'Tangent')
node.inputs['Direction'].default_value = (.2,.4,.7)
plane.rotation_euler.z = .6
scene.view_layers[0].update()
expected = plane.matrix_world.to_3x3() @ (Euler((.2,.4,.7)).to_matrix().inverted() @ Vector((1,0,0)))
expected.z = 0
expected.normalize()
dot = mat.node_tree.nodes.new('ShaderNodeVectorMath')
dot.operation = 'DOT_PRODUCT'
mat.node_tree.links.new(node.outputs['Tangent'],dot.inputs[0])
dot.inputs[1].default_value = expected
mat.node_tree.links.new(dot.outputs['Value'],emission.inputs['Color'])
evaluate('Rotated brush tangent follows surface in world space',1,.001)
plane.rotation_euler.z = 0
scene.view_layers[0].update()

use(imperfections,'Scratch Mask')
for name in ('Edge Wear','Surface Wear','Dust','Oil'):
    node.inputs[name].default_value = 0
for channel in ('Wear Mask','Scratch Mask','Smudge Mask','Dust Mask','Oil Mask'):
    output_channel(channel)
    evaluate('Disabled '+channel,0,.000001)
node.inputs['Surface Wear'].default_value = 1
node.inputs['Scratch Tile mm'].default_value = 4
output_channel('Scratch Mask')
scratch = evaluate('Shared image scratches enabled')[0]
assert scratch > .0001
output_channel('Smudge Mask')
assert evaluate('Shared handling smudges enabled')[0] > .01
output_channel('Roughness')
assert evaluate('Marks alter bare metal roughness')[0] > .3
node.inputs['Dust'].default_value = 1
output_channel('Dust Mask')
assert evaluate('Shared upward dust enabled')[0] > .01
node.inputs['Oil'].default_value = 1
node.inputs['Oil Patch mm'].default_value = 4
output_channel('Oil Mask')
assert evaluate('Independent image oil enabled')[0] > .01
# Compare metal adapter scratch mask with the exact shared group result.
use(shared,'Scratch Mask')
node.inputs['Surface Scratches'].default_value = 1
node.inputs['Scratch Tile mm'].default_value = 4
node.inputs['Surface Seed'].default_value = 7
evaluate('Metal and shared scratch masks agree',scratch,.00001)

# Probe public controls by adding diagnostics only to disposable wrapper copies.
def public(family,channel):
    source = bpy.data.materials['UM '+family+' Metal'].node_tree.nodes['Metal Controls']
    wrapper = source.node_tree.copy()
    inner = wrapper.nodes['Advanced Metal Settings']
    inner.node_tree = inner.node_tree.copy()
    for name in ('Base Color','Roughness','Height mm','Scratch Mask','Smudge Mask','Dust Mask','Oil Mask'):
        wrapper.interface.new_socket(name=name,in_out='OUTPUT',socket_type='NodeSocketColor' if name == 'Base Color' else 'NodeSocketFloat')
        wrapper.links.new(inner.outputs[name],wrapper.nodes['Outputs'].inputs[name])
    use(wrapper,channel)
    node.inputs['Base Metal'].default_value = 'Steel'
    for name in ('Edge Wear','Surface Wear','Dust','Oil'):
        node.inputs[name].default_value = 0
    return inner

inner = public('Cast','Base Color')
node.inputs['Color Tint'].default_value = (.5,.5,.5,1)
evaluate('Public color tint',(.275,.29,.3))
output_channel('Roughness')
node.inputs['Roughness'].default_value = .41
evaluate('Public roughness',.41,.06)
output_channel('Height mm')
node.inputs['Surface Detail'].default_value = 0
evaluate('Public detail disables cast relief',0,.000001)
node.inputs['Surface Detail'].default_value = 1
node.inputs['Grain Scale'].default_value = 2
reference = evaluate('Public grain scale 2')[0]
# Equal physical mm coordinates after a scene-unit change must give same texture.
inner.inputs['Scene Unit m'].default_value = .01
coordinate_node = inner.node_tree.nodes['Coordinates mm']
# Use a static point rather than resize geometry / camera for this check.
for link in list(coordinate_node.inputs[0].links):
    inner.node_tree.links.remove(link)
coordinate_node.inputs[0].default_value = (.12,.23,.34)
a = evaluate('Centimeter scene point')[0]
inner.inputs['Scene Unit m'].default_value = 1
coordinate_node.inputs[0].default_value = (.0012,.0023,.0034)
b = evaluate('Equivalent meter scene point')[0]
assert abs(a-b) < .000001
output_channel('Scratch Mask')
node.inputs['Surface Wear'].default_value = 1
scratch_a = evaluate('Scratches at grain scale 2')[0]
node.inputs['Grain Scale'].default_value = .5
scratch_b = evaluate('Scratches at grain scale 0.5')[0]
assert abs(scratch_a-scratch_b) < .000001

bpy.context.window.scene = gallery
if '--render-eevee' in sys.argv:
    gallery.render.engine = 'BLENDER_EEVEE'
    gallery.render.resolution_percentage = 100
    gallery.render.filepath = str(DIRECTORY/'unified_metal_eevee.png')
    bpy.ops.render.render(write_still=True)
report = {'blender':bpy.app.version_string,'passed':True,'check_count':len(checks),
          'public_inputs':public_inputs,'separate_finish_groups':len(structures),
          'shared_imperfections':True,'packed_images':2,'checks':checks,
          'eevee_render':'--render-eevee' in sys.argv}
(DIRECTORY/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('PASS',len(checks),'rendered checks; separate finishes; shared masks; public controls; packed images')
