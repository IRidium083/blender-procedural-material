"""Verify random short fibers and independent density/visibility controls, then render Eevee gallery."""
import json
from pathlib import Path
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
shared_finish = next(g for g in bpy.data.node_groups if g.get('shared_finish_version') == 2)
scratch_image = shared_finish.nodes['Shared Scratch Image'].image
assert scratch_image.packed_file and len(scratch_image.pixels) > 0
assert scratch_image.colorspace_settings.name == 'Non-Color'
assert shared_finish.nodes['Scratch Coverage'].inputs[0].links[0].from_node.type == 'TEX_IMAGE'

master = bpy.data.materials['Fiberglass Reinforced Plastic'].node_tree.nodes['Glass Fiber Controls'].node_tree
shader = master.nodes['Fiberglass Reinforced Plastic']
assert shader.inputs['Metallic'].default_value == 0
assert not shader.inputs['Tangent'].is_linked
assert shader.inputs['Anisotropic'].default_value == 0
assert not any('Bundle' in n.name or 'Weave' in n.name for n in master.nodes)
assert not any(n.type == 'TEX_IMAGE' for n in master.nodes)
for obj in gallery.objects:
    if obj.type == 'MESH':
        assert obj.data.uv_layers.active
        assert obj.active_material

scene = bpy.data.scenes.new('Chopped Fiber Verification')
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=2)
plane = bpy.context.object
mat = bpy.data.materials.new('FRP Test')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
group = mat.node_tree.nodes.new('ShaderNodeGroup')
group.node_tree = master.copy()
out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
emit = mat.node_tree.nodes.new('ShaderNodeEmission')
mat.node_tree.links.new(emit.outputs[0], out.inputs['Surface'])
group.inputs['UV Width mm'].default_value = 30
group.inputs['UV Height mm'].default_value = 30
cam = bpy.data.objects.new('Test Camera', bpy.data.cameras.new('Test Camera'))
scene.collection.objects.link(cam)
cam.location = (0,0,1)
cam.data.type, cam.data.ortho_scale = 'ORTHO', 2
scene.camera = cam
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
results = []


def sample(name, channel='Fiber Mask'):
    mat.node_tree.links.new(group.outputs[channel], emit.inputs['Color'])
    with tempfile.TemporaryDirectory(prefix='frp_test_') as folder:
        scene.render.filepath = str(Path(folder)/'sample.exr')
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        values = list(image.pixels)[0::4]
        bpy.data.images.remove(image)
    mean = sum(values)/len(values)
    results.append({'check': name, 'coverage': mean})
    return values, mean


group.inputs['Fiber Density'].default_value = 0
_, mean = sample('Zero density removes fibers')
assert mean < 0.000001
group.inputs['Fiber Density'].default_value = 0.75
original, mean = sample('Sparse chopped fibers')
assert 0.003 < mean < 0.3, mean
assert max(original) > 0.5 and min(original) == 0
group.inputs['Seed'].default_value = 12
changed, _ = sample('Seed changes fiber locations')
assert sum(abs(a-b) for a,b in zip(original, changed))/len(original) > 0.005
group.inputs['Seed'].default_value = 3
group.inputs['Fiber Width mm'].default_value = 0.15
_, wider = sample('Wider fibers increase coverage')
assert wider > mean * 1.5
group.inputs['Fiber Visibility'].default_value = 0
_, hidden = sample('Zero visibility embeds fibers invisibly', 'Visible Fibers')
assert hidden < 0.000001
bpy.context.window.scene = gallery
gallery.render.engine = 'BLENDER_EEVEE'
gallery.render.filepath = str(DIRECTORY/'glassfiber_eevee.png')
bpy.ops.render.render(write_still=True)
(DIRECTORY/'validation.json').write_text(json.dumps({'passed':True,'checks':results},indent=2),encoding='utf-8')
print('PASS: random short fibers, density, seed, width and visibility; Eevee render')
