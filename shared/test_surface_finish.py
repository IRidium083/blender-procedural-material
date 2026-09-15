"""Contract tests for shared marks and arbitrary-shader deposits in both engines."""
import json
from pathlib import Path
import sys
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY.parent))
from shared.surface_finish import build_marks_group,build_deposits_group,build_patch_group

marks = build_marks_group()
deposits = build_deposits_group()
assert build_marks_group() == marks and build_deposits_group() == deposits
assert not any(n.type.startswith('BSDF') or n.type == 'BSDF_PRINCIPLED' for n in marks.nodes)
assert marks.nodes['Shared Surface Patches'].node_tree == build_patch_group()
coverage = deposits.nodes['Shared Deposit Coverage'].node_tree
assert coverage.nodes['Shared Surface Patches'].node_tree == build_patch_group()
assert marks.nodes['Shared Scratch Image'].image.packed_file
scene = bpy.data.scenes.new('Surface Deposits Contract')
bpy.context.window.scene = scene
scene.world = bpy.data.worlds.new('Uniform Test World')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.5,.5,.5,1)
bpy.ops.mesh.primitive_plane_add(size=2)
plane = bpy.context.object
mat = bpy.data.materials.new('Shader In Out Contract')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
nodes,links = mat.node_tree.nodes,mat.node_tree.links
emit = nodes.new('ShaderNodeEmission')
metal = nodes.new('ShaderNodeBsdfPrincipled')
metal.inputs['Metallic'].default_value = 1
metal.inputs['Base Color'].default_value = (.12,.25,.45,1)
mix = nodes.new('ShaderNodeMixShader')
mix.inputs[0].default_value = .35
links.new(emit.outputs[0],mix.inputs[1])
links.new(metal.outputs[0],mix.inputs[2])
group = nodes.new('ShaderNodeGroup')
group.node_tree = deposits
out = nodes.new('ShaderNodeOutputMaterial')
cam = bpy.data.objects.new('Contract Camera',bpy.data.cameras.new('Contract Camera'))
scene.collection.objects.link(cam)
cam.location = (0,0,1)
cam.data.type,cam.data.ortho_scale = 'ORTHO',1
scene.camera = cam
scene.render.resolution_x = scene.render.resolution_y = 24
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
scene.cycles.samples,scene.cycles.use_denoising = 32,False
checks = []


def render(label,socket):
    links.new(socket,out.inputs['Surface'])
    with tempfile.TemporaryDirectory(prefix='deposits_contract_') as folder:
        scene.render.filepath = str(Path(folder)/'value.exr')
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath,check_existing=False)
        px = list(img.pixels)
        bpy.data.images.remove(img)
    rgb = [sum(px[c::4])/(len(px)//4) for c in range(3)]
    checks.append({'engine':scene.render.engine,'check':label,'mean_rgb':rgb})
    return rgb


def error(a,b):
    return max(abs(x-y) for x,y in zip(a,b))


for engine in ('CYCLES','BLENDER_EEVEE'):
    scene.render.engine = engine
    for source in (emit.outputs[0],metal.outputs[0],mix.outputs[0]):
        emit.inputs['Color'].default_value = (.2,.4,.7,1)
        group.inputs['Dust'].default_value = 0
        group.inputs['Additional Coverage'].default_value = 0
        links.new(source,group.inputs['Surface'])
        direct = render(source.node.type+' direct',source)
        through = render(source.node.type+' zero deposits',group.outputs['Shader'])
        assert error(direct,through) < .0001,(engine,direct,through)
    links.new(emit.outputs[0],group.inputs['Surface'])
    for amount in (1,.5):
        group.inputs['Additional Coverage'].default_value = amount
        emit.inputs['Color'].default_value = (.2,.4,.7,1)
        a = render('Coverage '+str(amount)+' first incoming surface',group.outputs['Shader'])
        emit.inputs['Color'].default_value = (.8,.1,.2,1)
        b = render('Coverage '+str(amount)+' second incoming surface',group.outputs['Shader'])
        expected = [.6*(1-amount),-.3*(1-amount),-.5*(1-amount)]
        assert error([y-x for x,y in zip(a,b)],expected) < .015,(engine,amount,a,b)
report = {'passed':True,'checks':checks,'contract':'Zero coverage preserves arbitrary shader; full coverage replaces it; partial coverage blends.'}
(DIRECTORY/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('PASS',len(checks),'shared deposit shader contract checks')
