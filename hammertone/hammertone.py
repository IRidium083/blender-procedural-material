"""Procedural hammered metallic paint. Run on selected meshes or --preview --render."""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parent))
try:
    from shared.surface_finish import Builder, build_patch_group, build_deposits_group
except ModuleNotFoundError:
    scope = {'__name__': 'shared_surface_finish'}
    exec(bpy.data.texts['shared_surface_finish.py'].as_string(), scope)
    Builder, build_patch_group, build_deposits_group = (scope[n] for n in
        ('Builder', 'build_patch_group', 'build_deposits_group'))
try:
    from render_utils import configure_cycles
except ModuleNotFoundError:
    scope = {'__name__': 'render_utils'}
    exec(bpy.data.texts['render_utils.py'].as_string(), scope)
    configure_cycles = scope['configure_cycles']


def build_core():
    g = Builder('Hammertone - Paint Structure v1', 'hammertone_version')
    color = g.input('Paint Color', (.075, .16, .23, 1), 'Color')
    size = g.input('Cell Size mm', 2.8, limits=(.3, 15))
    amount = g.input('Hammer Amount', .8, limits=(0, 1))
    rough = g.input('Roughness', .3, limits=(.08, .8))
    metal = g.input('Metallic Sheen', .65, limits=(0, 1))
    coat = g.input('Gloss Coat', .65, limits=(0, 1))
    smudges = g.input('Smudges', .08, limits=(0, 1))
    dust = g.input('Dust', 0, limits=(0, 1))
    units = g.input('Scene Unit m', bpy.context.scene.unit_settings.scale_length, limits=(.000001, 1000))
    seed = g.input('Seed', 5, limits=(0, 1000))
    coord = g.node('ShaderNodeTexCoord', 'Object Coordinates')
    mm = g.vector('SCALE', coord.outputs['Object'], g.calc('MULTIPLY', units, 1000), 'Coordinates mm')
    xyz = g.vector('SCALE', mm, g.calc('DIVIDE', 1, g.calc('MAXIMUM', size, .001)), 'Physical Cell Scale')
    xyz = g.vector('ADD', xyz, g.vector('SCALE', (1.31, 2.17, .73), seed, 'Seed Offset'), 'Seeded Cells')
    noise = g.node('ShaderNodeTexNoise', 'Irregular Paint Flow')
    g.set(noise.inputs['Vector'], xyz)
    noise.inputs['Scale'].default_value = 1.7
    noise.inputs['Detail'].default_value = 2
    warp = g.vector('SCALE', g.vector('SUBTRACT', noise.outputs['Color'], (.5, .5, .5), 'Centered Flow'), .38, 'Small Flow Distortion')
    warped = g.vector('ADD', xyz, warp, 'Distorted Cell Coordinates')
    cells = g.node('ShaderNodeTexVoronoi', 'Hammered Paint Cells')
    cells.feature = 'F1'
    cells.distance = 'EUCLIDEAN'
    cells.inputs['Scale'].default_value = 1
    g.set(cells.inputs['Vector'], warped)
    edges = g.node('ShaderNodeTexVoronoi', 'Cell Boundaries')
    edges.feature = 'DISTANCE_TO_EDGE'
    edges.inputs['Scale'].default_value = 1
    g.set(edges.inputs['Vector'], warped)
    profile = g.node('ShaderNodeMapRange', 'Rounded Shallow Basins')
    profile.interpolation_type = 'SMOOTHSTEP'
    profile.clamp = True
    g.set(profile.inputs['Value'], cells.outputs['Distance'])
    profile.inputs['From Min'].default_value = 0
    profile.inputs['From Max'].default_value = .85
    profile.inputs['To Min'].default_value = 0
    profile.inputs['To Max'].default_value = 1
    rim = g.node('ShaderNodeMapRange', 'Narrow Dark Paint Boundaries')
    rim.interpolation_type = 'SMOOTHSTEP'
    rim.clamp = True
    g.set(rim.inputs['Value'], edges.outputs['Distance'])
    rim.inputs['From Min'].default_value = .005
    rim.inputs['From Max'].default_value = .09
    variation = g.calc('ADD', .68, g.calc('MULTIPLY', cells.outputs['Color'], .5))
    radial = g.calc('SUBTRACT', 1.2, g.calc('MULTIPLY', profile.outputs[0], .75), 'Pigment Pools in Cell Centers')
    tone = g.calc('MULTIPLY', g.calc('ADD', .65, g.calc('MULTIPLY', rim.outputs[0], .35)), g.calc('MULTIPLY', variation, radial))
    tone = g.mix(amount, 1, tone, 'Hammer Color Amount')
    tint = g.mix(1, color, tone, 'Metallic Pigment in Paint')
    tint_node = tint.node
    tint_node.blend_type = 'MULTIPLY'
    relief = g.calc('MULTIPLY', amount, .16, 'Relief mm')
    grain = g.node('ShaderNodeTexNoise', 'Fine Paint Surface')
    g.set(grain.inputs['Vector'], warped)
    grain.inputs['Scale'].default_value = 8
    grain.inputs['Detail'].default_value = 2
    height = g.calc('ADD', profile.outputs[0], g.calc('MULTIPLY', grain.outputs['Fac'], .045), 'Hammered Cells and Fine Paint Texture')
    bump = g.node('ShaderNodeBump', 'Shallow Paint Relief')
    bump.inputs['Strength'].default_value = 1
    g.set(bump.inputs['Height'], height)
    g.set(bump.inputs['Distance'], g.calc('DIVIDE', g.calc('MULTIPLY', relief, .001), units))
    patches = g.group('Shared Smudge Patches', build_patch_group())
    g.set(patches.inputs['Coordinates mm'], mm)
    patches.inputs['Patch Size mm'].default_value = 18
    smudge = g.calc('MULTIPLY', patches.outputs['Patches'], smudges, 'Smudge Coverage')
    r = g.calc('ADD', rough, g.calc('MULTIPLY', g.calc('SUBTRACT', noise.outputs['Fac'], .5), g.calc('MULTIPLY', amount, .12)))
    r = g.calc('ADD', r, g.calc('MULTIPLY', smudge, .2), 'Uneven Paint Roughness', True)
    shader = g.node('ShaderNodeBsdfPrincipled', 'Metallic Paint and Clear Binder')
    for name, value in [('Base Color', tint), ('Metallic', metal), ('Roughness', r),
                        ('Normal', bump.outputs['Normal']), ('Coat Normal', bump.outputs['Normal']),
                        ('Coat Weight', coat), ('Coat Roughness', g.calc('ADD', .12, g.calc('MULTIPLY', smudge, .3)))]:
        g.set(shader.inputs[name], value)
    shader.inputs['IOR'].default_value = 1.5
    shader.inputs['Coat IOR'].default_value = 1.46
    deposits = g.group('Shared Surface Deposits', build_deposits_group())
    for name, value in [('Surface', shader.outputs[0]), ('Coordinates mm', mm), ('Dust', dust), ('Dust Normal', bump.outputs['Normal'])]:
        g.set(deposits.inputs[name], value)
    g.output('Shader', deposits.outputs['Shader'], 'Shader')
    g.output('Base Color', tint, 'Color')
    for name, value in [('Cell Profile', profile.outputs[0]), ('Relief mm', relief), ('Roughness', r),
                        ('Dust Mask', deposits.outputs['Dust Mask']), ('Smudge Mask', smudge)]:
        g.output(name, value)
    return g.finish()


def public_group(core):
    g = Builder('Hammertone - Material Controls', 'hammertone_controls_version')
    inner = g.group('Advanced Paint Settings', core)
    for socket in core.interface.items_tree:
        if socket.item_type != 'SOCKET' or socket.in_out != 'INPUT' or socket.name in {'Seed', 'Scene Unit m'}:
            continue
        kind = socket.socket_type.removeprefix('NodeSocket')
        limits = (socket.min_value, socket.max_value) if kind == 'Float' else None
        g.set(inner.inputs[socket.name], g.input(socket.name, socket.default_value, kind, limits))
    g.output('Shader', inner.outputs['Shader'], 'Shader')
    return g.finish()


def make_material(name='Hammertone - Blue', group=None, **settings):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = mat.use_fake_user = True
    mat.node_tree.nodes.clear()
    n = mat.node_tree.nodes.new('ShaderNodeGroup')
    n.node_tree, n.name, n.width = group or public_group(build_core()), 'Hammertone Controls', 300
    for key, value in settings.items():
        n.inputs[key].default_value = value
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (420, 0)
    mat.node_tree.links.new(n.outputs['Shader'], out.inputs['Surface'])
    mat['hammertone_version'] = 1
    mat.diffuse_color = n.inputs['Paint Color'].default_value
    return mat


def preview(render):
    scene = bpy.data.scenes.new('Hammertone Paint Studio')
    bpy.context.window.scene = scene
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1
    group = public_group(build_core())
    mats = [make_material(group=group),
            make_material('Hammertone - Silver', group, **{'Paint Color': (.36, .38, .4, 1), 'Metallic Sheen': .8}),
            make_material('Hammertone - Green', group, **{'Paint Color': (.07, .115, .065, 1)})]
    bodies = []
    for i, mat in enumerate(mats):
        x = (i-1)*.125
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, .065, 0))
        block = bpy.context.object
        block.name = mat.name+' 100mm Panel'
        block.dimensions = (.105, .1, .008)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = block.modifiers.new('Rounded Painted Edge', 'BEVEL')
        bevel.width, bevel.segments = .003, 5
        block.modifiers.new('Face Normals', 'WEIGHTED_NORMAL')
        block.data.materials.append(mat)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=.049, location=(x, -.066, .01))
        sphere = bpy.context.object
        sphere.name = mat.name+' 98mm Sphere'
        sphere.data.materials.append(mat)
        for face in sphere.data.polygons:
            face.use_smooth = True
        bodies.append(block)
        data = bpy.data.curves.new(mat.name+' Label', 'FONT')
        data.body, data.align_x, data.size = mat.name.split(' - ')[1].upper(), 'CENTER', .006
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = (x, -.14, -.025)
    scene.world = bpy.data.worlds.new('Hammertone Studio World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.18, .2, .24, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .45
    for name, pos, power, size in [('Key', (-.25, -.18, .4), 9, .2), ('Fill', (.3, -.05, .3), 4, .18), ('Rim', (0, .3, .25), 3, .13)]:
        obj = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
        obj.data.energy, obj.data.shape, obj.data.size = power, 'DISK', size
    cam = bpy.data.objects.new('Hammertone Camera', bpy.data.cameras.new('Hammertone Camera'))
    scene.collection.objects.link(cam)
    cam.location = (.17, -.34, .5)
    cam.rotation_euler = (Vector((0, -.01, 0))-cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type, cam.data.ortho_scale, cam.data.clip_start = 'ORTHO', .46, .001
    scene.camera = cam
    configure_cycles(scene)
    scene.cycles.samples, scene.cycles.use_denoising = 64, True
    scene.render.resolution_x, scene.render.resolution_y = 1500, 1150
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(DIRECTORY/'hammertone_preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    bodies[0].select_set(True)
    bpy.context.view_layer.objects.active = bodies[0]
    for name, path in [('hammertone.py', Path(__file__)), ('shared_surface_finish.py', DIRECTORY.parent/'shared/surface_finish.py')]:
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        text.clear()
        text.write(path.read_text(encoding='utf-8'))
        text.filepath = str(path.resolve())
    bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY/'hammertone.blend'))
    if render:
        bpy.ops.render.render(write_still=True)
        target = bodies[0].location+Vector((0, 0, .004))
        cam.location = target+Vector((.025, .015, .1))
        cam.rotation_euler = (target-cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = .034
        scene.render.resolution_x = scene.render.resolution_y = 1000
        scene.render.filepath = str(DIRECTORY/'hammertone_detail.png')
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.preview:
        preview(args.render)
    else:
        targets = [o for o in bpy.context.selected_objects if o.type == 'MESH']
        if not targets:
            raise RuntimeError('Select mesh objects before running hammertone.py.')
        material = make_material()
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = material
            else:
                obj.data.materials.append(material)


if __name__ == '__main__':
    main()
