"""Render-backed checks of physical scale, controls, portable sources and Eevee."""
import json
from pathlib import Path
import tempfile
import bpy

DIRECTORY = Path(__file__).resolve().parent
gallery = bpy.context.scene
assert gallery.render.engine == 'CYCLES'
# The delivered preview keeps the GPU choice, independent of temporary tests.
saved_device = gallery.cycles.device
materials = [m for m in bpy.data.materials if m.get('hammertone_version') == 1]
assert len(materials) == 3
expected = ['Paint Color', 'Cell Size mm', 'Hammer Amount', 'Roughness', 'Metallic Sheen', 'Gloss Coat', 'Smudges', 'Dust']
cores = set()
for material in materials:
    assert material.use_fake_user and not material.asset_data
    wrapper = material.node_tree.nodes['Hammertone Controls'].node_tree
    assert [s.name for s in wrapper.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT'] == expected
    cores.add(wrapper.nodes['Advanced Paint Settings'].node_tree)
assert len(cores) == 1
core = cores.pop()
assert core.nodes['Shared Surface Deposits'].node_tree.get('surface_deposits_version') == 1
assert not any(n.type == 'TEX_IMAGE' for tree in bpy.data.node_groups for n in tree.nodes)
# Force the embedded-source fallback: importing from the repository is disabled.
import builtins
real_import = builtins.__import__
def embedded_import(name, *args, **kwargs):
    if name in {'shared.surface_finish', 'render_utils'}:
        raise ModuleNotFoundError(name)
    return real_import(name, *args, **kwargs)
namespace = {'__name__': 'portable_test', '__file__': 'C:/missing/hammertone.py',
             '__builtins__': dict(vars(builtins), __import__=embedded_import)}
exec(bpy.data.texts['hammertone.py'].as_string(), namespace)
assert namespace['build_deposits_group']() == core.nodes['Shared Surface Deposits'].node_tree
scene = bpy.data.scenes.new('Hammertone Numeric Checks')
bpy.context.window.scene = scene
bpy.ops.mesh.primitive_plane_add(size=.04)
plane = bpy.context.object
mat = bpy.data.materials.new('Numeric Test')
mat.use_nodes = True
mat.node_tree.nodes.clear()
plane.data.materials.append(mat)
group = mat.node_tree.nodes.new('ShaderNodeGroup')
group.node_tree = core.copy()
out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
emission = mat.node_tree.nodes.new('ShaderNodeEmission')
mat.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
cam = bpy.data.objects.new('Numeric Camera', bpy.data.cameras.new('Numeric Camera'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, 0, .1)
cam.data.type, cam.data.ortho_scale, cam.data.clip_start = 'ORTHO', .03, .001
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples, scene.cycles.use_denoising = 4, False
scene.render.resolution_x = scene.render.resolution_y = 96
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format, scene.render.image_settings.color_depth = 'OPEN_EXR', '32'
checks = []


def sample(label, channel, target=None):
    mat.node_tree.links.new(group.outputs[channel], emission.inputs['Color'])
    with tempfile.TemporaryDirectory(prefix='hammertone_check_') as folder:
        scene.render.filepath = str(Path(folder)/'value.exr')
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = list(img.pixels)
        bpy.data.images.remove(img)
    values = pixels[0::4]
    mean = sum(values)/len(values)
    if target is not None:
        rgb = [sum(pixels[c::4])/len(values) for c in range(3)]
        targets = [target]*3 if isinstance(target, (int, float)) else target
        assert max(abs(a-b) for a, b in zip(rgb, targets)) < .00002, (label, rgb, targets)
    checks.append({'check': label, 'mean': mean})
    return values


base = sample('Hammered cells vary across the paint', 'Cell Profile')
assert max(base)-min(base) > .5
assert all(0 <= v <= 1.00001 for v in base)
sample('Default relief is 128 micrometers', 'Relief mm', .128)
group.inputs['Hammer Amount'].default_value = 0
sample('Hammer zero removes relief', 'Relief mm', 0)
sample('Hammer zero removes pigment pattern', 'Base Color', (.075, .16, .23))
group.inputs['Smudges'].default_value = 0
sample('Hammer zero and smudges zero give requested roughness', 'Roughness', .3)
sample('Smudges disabled', 'Smudge Mask', 0)
sample('Dust disabled', 'Dust Mask', 0)
group.inputs['Smudges'].default_value = 1
assert max(sample('Shared smudges respond', 'Smudge Mask')) > .1
group.inputs['Dust'].default_value = 1
assert max(sample('Shared dust responds', 'Dust Mask')) > .1
group.inputs['Hammer Amount'].default_value = .8
group.inputs['Cell Size mm'].default_value = 5.6
large = sample('Larger cell size changes the pattern', 'Cell Profile')
assert sum(abs(a-b) for a, b in zip(base, large))/len(base) > .08
# Double the geometry AND cell size: normalized pattern must be unchanged.
for vertex in plane.data.vertices:
    vertex.co *= 2
plane.data.update()
cam.data.ortho_scale *= 2
same = sample('Object dimensions and cell size scale consistently', 'Cell Profile')
assert sum(abs(a-b) for a, b in zip(base, same))/len(base) < .0002
# Centimeter scene units with geometry/camera scaled inversely preserve mm.
group.inputs['Scene Unit m'].default_value = .01
for vertex in plane.data.vertices:
    vertex.co *= 100
plane.data.update()
cam.location.z *= 100
cam.data.ortho_scale *= 100
centimeter = sample('Centimeter scene units preserve physical pattern', 'Cell Profile')
assert sum(abs(a-b) for a, b in zip(same, centimeter))/len(same) < .0002
bpy.context.window.scene = gallery
gallery.render.engine = 'BLENDER_EEVEE'
gallery.render.resolution_percentage = 70
gallery.render.filepath = str(DIRECTORY/'hammertone_eevee.png')
bpy.ops.render.render(write_still=True)
report = {'passed': True, 'blender': bpy.app.version_string, 'checks': checks,
          'materials': [m.name for m in materials], 'public_inputs': expected,
          'procedural': True, 'embedded_source_fallback': True,
          'saved_cycles_device': saved_device, 'renderers': ['Cycles', 'Eevee']}
(DIRECTORY/'validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print('PASS', len(checks), 'Hammertone render checks, embedded sources and Eevee')
