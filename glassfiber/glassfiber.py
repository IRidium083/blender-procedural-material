"""Short glass-fiber reinforced plastic for Blender 5.2.
UV-mapped random chopped fibers with physical dimensions, shared packed scratch image for optional surface imperfections.
Run on selected meshes, or use --preview --render for the sample scene.
"""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
try:
    from render_utils import configure_cycles
except ModuleNotFoundError:
    _render_namespace = {'__name__':'render_utils'}
    _render_source = bpy.data.texts.get('render_utils.py')
    if _render_source is None:
        raise RuntimeError('Keep render_utils.py in the material repository root.')
    exec(_render_source.as_string(),_render_namespace)
    configure_cycles = _render_namespace['configure_cycles']

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parent))
try:
    from shared.surface_finish import attach_finish
except ModuleNotFoundError:
    # Appended node groups are self-contained; embedded source also supports regeneration.
    _finish_source = bpy.data.texts.get('shared_surface_finish.py')
    if _finish_source is None:
        raise RuntimeError('Keep shared/surface_finish.py in the project root for regeneration.')
    _finish_namespace = {'__name__': 'shared_surface_finish'}
    exec(_finish_source.as_string(), _finish_namespace)
    attach_finish = _finish_namespace['attach_finish']
NAME = 'Fiberglass Reinforced Plastic'


class Graph:
    def __init__(self):
        self.tree = bpy.data.node_groups.new(NAME + ' - Surface', 'ShaderNodeTree')
        self.controls = self.node('NodeGroupInput', 'Material Controls')
        self.out = self.node('NodeGroupOutput', 'Outputs')

    def node(self, kind, name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 200
        return n

    def set(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def input(self, name, value, kind='Float', limits=None):
        socket = self.tree.interface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocket'+kind)
        if kind != 'Menu':
            socket.default_value = value
        if limits:
            socket.min_value, socket.max_value = limits
        return self.controls.outputs[name]

    def output(self, name, value, kind='Float'):
        self.tree.interface.new_socket(name=name, in_out='OUTPUT', socket_type='NodeSocket'+kind)
        self.set(self.out.inputs[name], value)

    def math(self, op, a, b=0, name=None):
        n = self.node('ShaderNodeMath', name or op)
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def mix(self, factor, a, b, name):
        n = self.node('ShaderNodeMixRGB', name)
        self.set(n.inputs[0], factor)
        for i, value in enumerate((a, b), 1):
            if isinstance(value, (int, float)):
                value = (value, value, value, 1)
            self.set(n.inputs[i], value)
        return n.outputs[0]

    def vector(self, op, a, b, name):
        n = self.node('ShaderNodeVectorMath', name)
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs['Scale'] if op == 'SCALE' else n.inputs[1], b)
        return n.outputs[0]

    def layout(self):
        depth = {n: 0 for n in self.tree.nodes}
        for _ in depth:
            for link in self.tree.links:
                depth[link.to_node] = max(depth[link.to_node], depth[link.from_node]+1)
        rows = {}
        for node, col in depth.items():
            row = rows.get(col, 0)
            node.location = (col*285, -row*310)
            rows[col] = row+1


def build_group():
    g = Graph()
    resin = g.input('Plastic Color', (0.075, 0.10, 0.055, 1), 'Color')
    fiber = g.input('Fiber Color', (0.44, 0.48, 0.31, 1), 'Color')
    width = g.input('UV Width mm', 200, limits=(0.01, 100000))
    height = g.input('UV Height mm', 120, limits=(0.01, 100000))
    length = g.input('Fiber Length mm', 3, limits=(0.1, 20))
    fiber_width = g.input('Fiber Width mm', 0.045, limits=(0.005, 0.5))
    density = g.input('Fiber Density', 0.75, limits=(0, 1))
    visibility = g.input('Fiber Visibility', 0.45, limits=(0, 1))
    relief = g.input('Fiber Relief mm', 0.004, limits=(0, 0.1))
    roughness = g.input('Roughness', 0.4, limits=(0.04, 1))
    seed = g.input('Seed', 3, limits=(0, 1000))
    units = g.input('Scene Unit m', bpy.context.scene.unit_settings.scale_length, limits=(0.000001, 1000))
    uv = g.node('ShaderNodeUVMap', 'Surface UV')
    size = g.node('ShaderNodeCombineXYZ', 'Physical UV Size')
    g.set(size.inputs['X'], width)
    g.set(size.inputs['Y'], height)
    mm = g.vector('MULTIPLY', uv.outputs['UV'], size.outputs[0], 'Surface Coordinates mm')
    cell_size = g.math('MULTIPLY', length, 1.6)
    masks = []
    for i, angle in enumerate((0, 1.13, 2.37)):
        rotate = g.node('ShaderNodeVectorRotate', f'Layer {i} Orientation')
        rotate.rotation_type = 'Z_AXIS'
        rotate.inputs['Angle'].default_value = angle
        g.set(rotate.inputs['Vector'], mm)
        offset = g.vector('SCALE', (0.71+i, 1.37+i*0.41, 0), seed, f'Layer {i} Seed Offset')
        position = g.vector('ADD', rotate.outputs[0], offset, f'Layer {i} Placement')
        cell = g.vector('SCALE', position, g.math('DIVIDE', 1, cell_size), f'Layer {i} Cells')
        index = g.vector('FLOOR', cell, (0,0,0), f'Layer {i} Cell Index')
        random = g.node('ShaderNodeTexWhiteNoise', f'Layer {i} Random Fiber')
        random.noise_dimensions = '3D'
        g.set(random.inputs['Vector'], index)
        channels = g.node('ShaderNodeSeparateXYZ', f'Layer {i} Random Parameters')
        g.set(channels.inputs[0], random.outputs['Color'])
        frac = g.vector('FRACTION', cell, (0,0,0), f'Layer {i} Cell Position')
        local = g.vector('SUBTRACT', frac, (0.5,0.5,0), f'Layer {i} Center')
        jitter = g.vector('SCALE', g.vector('SUBTRACT', random.outputs['Color'], (0.5,0.5,0.5), f'Layer {i} Jitter Center'), 0.3, f'Layer {i} Jitter')
        local = g.vector('SCALE', g.vector('SUBTRACT', local, jitter, f'Layer {i} Random Center'), cell_size, f'Layer {i} Local mm')
        orient = g.node('ShaderNodeVectorRotate', f'Layer {i} Random Angle')
        orient.rotation_type = 'Z_AXIS'
        g.set(orient.inputs['Vector'], local)
        g.set(orient.inputs['Angle'], g.math('MULTIPLY', channels.outputs['Z'], 2*math.pi))
        xy = g.node('ShaderNodeSeparateXYZ', f'Layer {i} Segment Coordinates')
        g.set(xy.inputs[0], orient.outputs[0])
        half_length = g.math('MULTIPLY', length, g.math('ADD', 0.25, g.math('MULTIPLY', channels.outputs['Y'], 0.25)))
        dx = g.math('MAXIMUM', g.math('SUBTRACT', g.math('ABSOLUTE', xy.outputs['X']), half_length), 0)
        dy = xy.outputs['Y']
        distance = g.math('SQRT', g.math('ADD', g.math('MULTIPLY', dx, dx), g.math('MULTIPLY', dy, dy)))
        radius = g.math('MULTIPLY', fiber_width, 0.5)
        soft = g.math('SUBTRACT', 1, g.math('DIVIDE', distance, radius))
        soft = g.math('MINIMUM', g.math('MAXIMUM', g.math('MULTIPLY', soft, 3), 0), 1)
        exists = g.math('LESS_THAN', random.outputs['Value'], density)
        masks.append(g.math('MULTIPLY', soft, exists, f'Layer {i} Short Fiber Mask'))
    mask = g.math('MAXIMUM', g.math('MAXIMUM', masks[0], masks[1]), masks[2], 'Random Chopped Fiber Mask')
    visible = g.math('MULTIPLY', mask, visibility, 'Embedded Fiber Visibility')
    noise = g.node('ShaderNodeTexNoise', 'Fine Mold Finish')
    g.set(noise.inputs['Vector'], mm)
    noise.inputs['Scale'].default_value = 4
    noise.inputs['Detail'].default_value = 2
    color = g.mix(visible, resin, fiber, 'Short Fibers in Plastic')
    rough = g.math('ADD', roughness, g.math('MULTIPLY', visible, 0.08))
    rough = g.math('ADD', rough, g.math('MULTIPLY', g.math('SUBTRACT', noise.outputs['Fac'], 0.5), 0.04))
    bump = g.node('ShaderNodeBump', 'Subtle Embedded Fiber Relief')
    bump.inputs['Strength'].default_value = 0.15
    g.set(bump.inputs['Height'], visible)
    g.set(bump.inputs['Distance'], g.math('DIVIDE', g.math('MULTIPLY', relief, 0.001), units))
    shader = g.node('ShaderNodeBsdfPrincipled', 'Fiberglass Reinforced Plastic')
    shader.inputs['Metallic'].default_value = 0
    shader.inputs['IOR'].default_value = 1.5
    shader.inputs['Coat Roughness'].default_value = 0.25
    g.set(shader.inputs['Base Color'], color)
    g.set(shader.inputs['Roughness'], g.math('MINIMUM', g.math('MAXIMUM', rough, 0.02), 1))
    g.set(shader.inputs['Normal'], bump.outputs['Normal'])
    finished = attach_finish(g, shader, mm, units, defaults={'Coat Amount': 0.25, 'Coat Roughness': 0.25, 'Surface Scratches': 0, 'Smudges': 0, 'Surface Dust': 0})
    g.output('Shader', finished, 'Shader')
    g.output('Fiber Mask', mask)
    g.output('Visible Fibers', visible)
    g.layout()
    return g.tree


def make_material(name=NAME, group=None, **settings):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (0.075, 0.10, 0.055, 1)
    mat.node_tree.nodes.clear()
    node = mat.node_tree.nodes.new('ShaderNodeGroup')
    node.node_tree, node.name, node.width = group or build_group(), 'Glass Fiber Controls', 320
    node.inputs['Clear Finish'].default_value = 'Clear Paint'
    for key, value in settings.items():
        node.inputs[key].default_value = value
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (450, 0)
    mat.node_tree.links.new(node.outputs['Shader'], out.inputs['Surface'])
    return mat


def preview(render):
    scene = bpy.data.scenes.new('Glass Fiber Studio')
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    group = build_group()
    coated = make_material(group=group)
    satin = make_material('FRP - Satin Plastic', group, **{'Coat Amount': 0.2, 'Roughness': 0.48})

    def panel(name, location, mat, curve):
        nx, ny = 64, 32
        width, height = 0.2, 0.12
        verts, faces = [], []
        for j in range(ny+1):
            for i in range(nx+1):
                x, y = (i/nx-0.5)*width, (j/ny-0.5)*height
                # Arc length along U is width, so UV mm matches the curved panel.
                if curve:
                    radius = 0.17
                    angle = x/radius
                    verts.append((radius*math.sin(angle), y, radius*(1-math.cos(angle))))
                else:
                    verts.append((x, y, 0))
        for j in range(ny):
            for i in range(nx):
                a = j*(nx+1)+i
                faces.append((a, a+1, a+nx+2, a+nx+1))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        uv = mesh.uv_layers.new(name='Surface UV')
        for face in mesh.polygons:
            face.use_smooth = True
            for loop in face.loop_indices:
                index = mesh.loops[loop].vertex_index
                uv.data[loop].uv = (index % (nx+1)/nx, index//(nx+1)/ny)
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.location = location
        mesh.materials.append(mat)
        solid = obj.modifiers.new('2mm Composite Sheet', 'SOLIDIFY')
        solid.thickness = 0.002
        return obj

    body = panel('Curved Glass Fiber 200x120mm', (0,0.09,0), coated, True)
    panel('Flat Satin Glass Fiber 200x120mm', (0,-0.07,0), satin, False)
    scene.world = bpy.data.worlds.new('Glass Fiber World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.15,0.18,0.22,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.4
    for name, pos, energy, size in [('Key',(-0.12,-0.25,0.4),10,0.25),('Fill',(0.3,0.05,0.2),5,0.2),('Rim',(0,0.3,0.35),10,0.18)]:
        obj = bpy.data.objects.new(name, bpy.data.lights.new(name,'AREA'))
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()
        obj.data.energy, obj.data.shape, obj.data.size = energy, 'DISK', size
    cam = bpy.data.objects.new('Glass Fiber Camera', bpy.data.cameras.new('Glass Fiber Camera'))
    scene.collection.objects.link(cam)
    cam.location = (0.29,-0.4,0.48)
    cam.rotation_euler = (Vector((0,0.015,0))-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type, cam.data.ortho_scale, cam.data.clip_start = 'ORTHO',0.4,0.001
    scene.camera = cam
    configure_cycles(scene)
    scene.cycles.samples, scene.cycles.use_denoising = 64, True
    scene.view_settings.exposure = -0.7
    scene.render.resolution_x = scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(DIRECTORY/'glassfiber_preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    text = bpy.data.texts.get('glassfiber.py') or bpy.data.texts.new('glassfiber.py')
    text.clear()
    text.write(Path(__file__).read_text(encoding='utf-8'))
    text.filepath = str(Path(__file__).resolve())
    shared_path = DIRECTORY.parent/'shared'/'surface_finish.py'
    shared_text = bpy.data.texts.get('shared_surface_finish.py') or bpy.data.texts.new('shared_surface_finish.py')
    if shared_path.exists():
        shared_text.clear()
        shared_text.write(shared_path.read_text(encoding='utf-8'))
    bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY/'glassfiber.blend'))
    if render:
        bpy.ops.render.render(write_still=True)
        # A close-up shows the short fibers; keep the saved gallery camera intact.
        flat = bpy.data.objects['Flat Satin Glass Fiber 200x120mm']
        cam.data.ortho_scale = 0.035
        cam.location = flat.location + Vector((0,-0.04,0.09))
        cam.rotation_euler = (flat.location-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath = str(DIRECTORY/'glassfiber_detail.png')
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
        if not targets or any(not o.data.uv_layers for o in targets):
            raise RuntimeError('Select UV-unwrapped mesh objects before running glassfiber.py.')
        mat = make_material()
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)


if __name__ == '__main__':
    main()
