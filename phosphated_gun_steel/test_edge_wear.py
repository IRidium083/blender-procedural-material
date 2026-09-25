"""Check wear on convex corners, concave corners, and rounded geometry."""
import json
from pathlib import Path
import tempfile
import bmesh
import bpy
from mathutils import Vector

directory = Path(__file__).resolve().parent
original = bpy.data.materials['Phosphated Gun Steel - Slightly Used']
source_group = original.node_tree.nodes['Group'].node_tree
assert any(s.name == 'Edge Wear Mask' for s in source_group.interface.items_tree)
mat = bpy.data.materials.new('Edge Wear Diagnostic')
mat.use_nodes = True
mat.node_tree.nodes.clear()
group = mat.node_tree.nodes.new('ShaderNodeGroup')
group.node_tree = source_group
emission = mat.node_tree.nodes.new('ShaderNodeEmission')
out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
mat.node_tree.links.new(group.outputs['Edge Wear Mask'], emission.inputs['Color'])
mat.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
group.inputs['Edge Wear'].default_value = 1
group.inputs['Scratches'].default_value = 0
scene = bpy.data.scenes.new('Sharp Edge Wear Diagnostic')
bpy.context.window.scene = scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
scene.render.film_transparent = True
cam = bpy.data.objects.new('Edge Camera', bpy.data.cameras.new('Edge Camera'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (.13, -.18, .12)
cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.type, cam.data.ortho_scale, cam.data.clip_start = 'ORTHO', .105, .0001


def render_values(obj):
    obj.hide_render = False
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    with tempfile.TemporaryDirectory(prefix='edge_wear_') as folder:
        scene.render.filepath = str(Path(folder)/'mask.exr')
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = list(img.pixels)
        bpy.data.images.remove(img)
    obj.hide_render = True
    # Count only opaque mesh pixels, excluding transparent background.
    values = [pixels[i] for i in range(0, len(pixels), 4) if pixels[i+3] > .5]
    lit = [v for v in values if v > .03]
    return {'max': max(values), 'mean': sum(values)/len(values),
            'lit_fraction': len(lit)/len(values),
            'lit_range': max(lit)-min(lit) if lit else 0}


bpy.ops.mesh.primitive_cube_add(size=.08)
cube = bpy.context.object
cube.name = 'True sharp box'
sharp = render_values(cube)
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=.04)
sphere = bpy.context.object
sphere.name = 'Smooth sphere'
for polygon in sphere.data.polygons:
    polygon.use_smooth = True
smooth = render_values(sphere)
bpy.ops.mesh.primitive_cube_add(size=.08)
rounded = bpy.context.object
rounded.name = 'Rounded box'
bevel = rounded.modifiers.new('Smooth 2.5mm Edges', 'BEVEL')
bevel.width, bevel.segments = .0025, 3
rounded_result = render_values(rounded)
bpy.ops.mesh.primitive_cube_add(size=.08)
concave_cube = bpy.context.object
concave_cube.name = 'Concave interior corner'
mesh_edit = bmesh.new()
mesh_edit.from_mesh(concave_cube.data)
bmesh.ops.reverse_faces(mesh_edit, faces=list(mesh_edit.faces))
mesh_edit.to_mesh(concave_cube.data)
mesh_edit.free()
cam.location = (.018, -.012, .005)
cam.rotation_euler = (Vector((-.04, .04, -.04))-cam.location).to_track_quat('-Z', 'Y').to_euler()
concave = render_values(concave_cube)
assert sharp['max'] > .05, (sharp, smooth)
assert sharp['lit_fraction'] > smooth['lit_fraction']*3, (sharp, smooth)
assert sharp['lit_range'] > .1, sharp
assert smooth['mean'] < .005, (sharp, smooth)
assert rounded_result['mean'] < .005, (sharp, rounded_result)
assert concave['max'] < .03, (sharp, concave)
cycles_result = {'sharp': sharp, 'smooth': smooth, 'rounded': rounded_result, 'concave': concave}
eevee_material = bpy.data.materials['Phosphated Gun Steel - Slightly Used - Eevee']
group.node_tree = eevee_material.node_tree.nodes['Group'].node_tree
edge_tags = bpy.data.node_groups['Gun Steel - Convex Sharp Edge Tags']
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = scene.render.resolution_y = 128
for obj in (cube, sphere, rounded, concave_cube):
    mod = obj.modifiers.new('Convex Edge Tags', 'NODES')
    mod.node_group = edge_tags
cam.location = (.13, -.18, .12)
cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
eevee_sharp = render_values(cube)
eevee_smooth = render_values(sphere)
eevee_rounded = render_values(rounded)
cam.location = (.018, -.012, .005)
cam.rotation_euler = (Vector((-.04, .04, -.04))-cam.location).to_track_quat('-Z', 'Y').to_euler()
eevee_concave = render_values(concave_cube)
for obj, expected in ((cube, 1), (sphere, 0), (rounded, 0), (concave_cube, 0)):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    values = [item.value for item in evaluated.attributes['gun_steel_convex_sharp_edge'].data]
    assert max(values) == expected, (obj.name, min(values), max(values))
assert eevee_sharp['max'] > .05, (eevee_sharp, eevee_smooth)
assert eevee_smooth['max'] < .03, eevee_smooth
assert eevee_rounded['max'] < .03, eevee_rounded
assert eevee_concave['max'] < .03, eevee_concave
report = {'passed': True, 'cycles': cycles_result,
          'eevee': {'sharp': eevee_sharp, 'smooth': eevee_smooth,
                    'rounded': eevee_rounded, 'concave': eevee_concave},
          'eevee_edge_tag_angle_degrees': 45,
          'saved_cycles_device': bpy.data.scenes['Phosphated Steel Studio'].cycles.device}
(directory/'edge_wear_validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print('PASS convex-only edge wear in Cycles and Eevee:', report)
