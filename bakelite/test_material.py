"""Validate pure procedural patterns, physical scale, controls, and Eevee."""
import json
from pathlib import Path
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
materials = [m for m in bpy.data.materials if m.get('bakelite_version') == 1]
assert len(materials) == 4
public_names = ['Resin Color','Filler Color','Pattern Scale','Pattern Amount','Direction','Seed','Roughness','Polish','Dust']
cores = {}
for material in materials:
    assert material.use_fake_user and not material.asset_data
    wrapper = material.node_tree.nodes['Bakelite Controls'].node_tree
    names = [s.name for s in wrapper.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT']
    assert names == public_names
    core = wrapper.nodes['Advanced Bakelite Settings'].node_tree
    cores[core['bakelite_pattern']] = core
assert len(cores) == 2
assert cores['Type 1 - Fragments'].nodes.get('Random Filler Packets')
assert not cores['Type 2 - Flow'].nodes.get('Random Filler Packets')
assert cores['Type 2 - Flow'].nodes.get('Long Resin Flow Strands')
shared = cores['Type 1 - Fragments'].nodes['Shared Resin Surface'].node_tree
assert all(c.nodes['Shared Resin Surface'].node_tree == shared for c in cores.values())
shader = shared.nodes['Molded Phenolic Resin']
assert shader.inputs['Metallic'].default_value == 0
assert shader.inputs['Transmission Weight'].default_value == 0
visited = set()
def check_procedural(tree):
    if tree in visited:
        return
    visited.add(tree)
    assert not any(n.type == 'TEX_IMAGE' for n in tree.nodes)
    for n in tree.nodes:
        if n.type == 'GROUP':
            check_procedural(n.node_tree)
for material in materials:
    check_procedural(material.node_tree)
# Embedded sources rebuild without the project or any image texture dependency.
namespace = {'__name__':'verify','__file__':'C:/missing/bakelite.py'}
exec(bpy.data.texts['bakelite.py'].as_string(),namespace)
assert namespace['resin_group'](namespace['Graph']) == shared
for obj in gallery.objects:
    if obj.type == 'MESH':
        assert tuple(obj.scale) == (1,1,1)
        assert obj.active_material

scene = bpy.data.scenes.new('Bakelite Verification')
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=.08)
plane = bpy.context.object
mat = bpy.data.materials.new('Bakelite Numeric Checks')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
node = mat.node_tree.nodes.new('ShaderNodeGroup')
out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
emit = mat.node_tree.nodes.new('ShaderNodeEmission')
mat.node_tree.links.new(emit.outputs[0],out.inputs['Surface'])
cam = bpy.data.objects.new('Test Camera',bpy.data.cameras.new('Test Camera'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0,0,.1)
cam.data.type,cam.data.ortho_scale = 'ORTHO',.065
cam.data.clip_start = .001
scene.render.engine = 'CYCLES'
scene.cycles.samples,scene.cycles.use_denoising = 4,False
scene.render.resolution_x = scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
checks = []


def sample(label,channel='Pattern Mask',expected=None):
    mat.node_tree.links.new(node.outputs[channel],emit.inputs['Color'])
    with tempfile.TemporaryDirectory(prefix='bakelite_check_') as folder:
        scene.render.filepath = str(Path(folder)/'value.exr')
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath,check_existing=False)
        pixels = list(image.pixels)
        bpy.data.images.remove(image)
    red = pixels[0::4]
    mean = sum(red)/len(red)
    variance = sum((v-mean)**2 for v in red)/len(red)
    checks.append({'check':label,'mean':mean,'variance':variance})
    if expected is not None:
        rgb = [sum(pixels[c::4])/len(red) for c in range(3)]
        assert max(abs(a-b) for a,b in zip(rgb,expected)) < .00001,(label,rgb,expected)
    return red,mean,variance


def difference(a,b):
    return sum(abs(x-y) for x,y in zip(a,b))/len(a)


for name,core in cores.items():
    node.node_tree = core.copy()
    for socket in core.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT':
            node.inputs[socket.name].default_value = socket.default_value
    sample(name+' clean deposits','Dust Mask',(0,0,0))
    node.inputs['Dust'].default_value = 1
    _,dust_mean,_ = sample(name+' enabled shared dust','Dust Mask')
    assert dust_mean > .01
    node.inputs['Dust'].default_value = 0
    original,mean,variance = sample(name+' varied pattern')
    assert .005 < mean < .7 and variance > .0005,(name,mean,variance)
    node.inputs['Seed'].default_value = 12
    changed,_,_ = sample(name+' new seed')
    assert difference(original,changed) > .02
    node.inputs['Seed'].default_value = 3
    node.inputs['Pattern Scale'].default_value = 2
    scaled,_,_ = sample(name+' doubled pattern size')
    assert difference(original,scaled) > .02
    node.inputs['Direction'].default_value = (0,0,1.57079633)
    rotated,_,_ = sample(name+' rotated pattern')
    assert difference(rotated,scaled) > .02
    node.inputs['Pattern Amount'].default_value = 0
    sample(name+' hidden filler','Visible Pattern',(0,0,0))
    sample(name+' solid resin color','Base Color',(.1,.021,.006))
    node.inputs['Resin Color'].default_value = (.08,.03,.01,1)
    sample(name+' editable resin palette','Base Color',(.08,.03,.01))
    rough_values,rmean,_ = sample(name+' uneven surface gloss','Surface Roughness')
    assert min(rough_values) >= .03 and max(rough_values) <= 1
    assert max(rough_values)-min(rough_values) > .005
    node.inputs['Roughness'].default_value = .6
    _,high,_ = sample(name+' roughness adjustment','Surface Roughness')
    assert abs(high-rmean-.28) < .00001
    node.inputs['Pattern Amount'].default_value = 1
    coordinates = node.node_tree.nodes['Coordinates mm']
    for link in list(coordinates.inputs[0].links):
        node.node_tree.links.remove(link)
    for i,point in enumerate(((.012,.023,.004),(.035,-.02,.007))):
        coordinates.inputs[0].default_value = point
        node.inputs['Scene Unit m'].default_value = 1
        a,_,_ = sample(name+' meter point '+str(i))
        coordinates.inputs[0].default_value = tuple(x*100 for x in point)
        node.inputs['Scene Unit m'].default_value = .01
        b,_,_ = sample(name+' centimeter point '+str(i))
        assert difference(a,b) < .00002

bpy.context.window.scene = gallery
gallery.render.engine = 'BLENDER_EEVEE'
gallery.render.filepath = str(DIRECTORY/'bakelite_eevee.png')
bpy.ops.render.render(write_still=True)
report = {'blender':bpy.app.version_string,'passed':True,'pure_procedural':True,
          'image_texture_nodes':0,'pattern_groups':list(cores),'shared_resin_group':shared.name,
          'materials':[m.name for m in materials],'public_controls':public_names,
          'checks':checks,'renderers':['Cycles','Eevee']}
(DIRECTORY/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('PASS',len(checks),'Bakelite checks; two distinct patterns; zero images; scale; Eevee')
