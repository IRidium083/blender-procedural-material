"""Blender 5.2 procedural wood and plywood. No images, UVs or add-ons required.
Run on selected meshes, or use --preview --render to create wood.blend.
"""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent


class Graph:
    def __init__(self):
        self.tree = bpy.data.node_groups.new('Wood - Physical Structure', 'ShaderNodeTree')
        self.gin = self.node('NodeGroupInput', 'Controls')
        self.gout = self.node('NodeGroupOutput', 'Outputs')

    def node(self, kind, name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 210
        return n

    def set(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def input(self, name, value, kind='Float', limits=None):
        s = self.tree.interface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocket'+kind)
        if kind != 'Menu':
            s.default_value = value
        if limits:
            s.min_value, s.max_value = limits
        return self.gin.outputs[name]

    def output(self, name, value, kind='Float'):
        self.tree.interface.new_socket(name=name, in_out='OUTPUT', socket_type='NodeSocket'+kind)
        self.set(self.gout.inputs[name], value)

    def scalar(self, op, a, b=0, name=None):
        n = self.node('ShaderNodeMath', name or op)
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def vector(self, op, a, b, name=None):
        n = self.node('ShaderNodeVectorMath', name or op)
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs['Scale'] if op == 'SCALE' else n.inputs[1], b)
        return n.outputs[0]

    def mix(self, factor, a, b, name):
        n = self.node('ShaderNodeMixRGB', name)
        self.set(n.inputs[0], factor)
        for i, value in enumerate((a, b), 1):
            if isinstance(value, (int, float)):
                value = (value, value, value, 1)
            self.set(n.inputs[i], value)
        return n.outputs[0]

    def noise(self, vector, scale, name, color=False):
        n = self.node('ShaderNodeTexNoise', name)
        self.set(n.inputs['Vector'], vector)
        self.set(n.inputs['Scale'], scale)
        n.inputs['Detail'].default_value = 3
        return n.outputs['Color' if color else 'Fac']

    def wave(self, vector, scale, name, kind='BANDS', axis='Y'):
        n = self.node('ShaderNodeTexWave', name)
        n.wave_type = kind
        if kind == 'BANDS':
            n.bands_direction = axis
        else:
            n.rings_direction = axis
        n.wave_profile = 'SIN'
        n.inputs['Distortion'].default_value = 0
        # Compensate Blender's sine-profile -pi/2 phase so ply boundaries
        # coincide with integer multiples of the requested thickness.
        n.inputs['Phase Offset'].default_value = math.pi/2
        self.set(n.inputs['Vector'], vector)
        self.set(n.inputs['Scale'], scale)
        return n.outputs['Fac']

    def layout(self):
        depths = {n: 0 for n in self.tree.nodes}
        for _ in depths:
            for link in self.tree.links:
                depths[link.to_node] = max(depths[link.to_node], depths[link.from_node]+1)
        rows = {}
        for n, depth in depths.items():
            row = rows.get(depth, 0)
            n.location = (depth*290, -row*310)
            rows[depth] = row+1


def build_group():
    g = Graph()
    mode = g.input('Structure', None, 'Menu')
    menu = g.node('GeometryNodeMenuSwitch', 'Structure Selection')
    menu.data_type = 'INT'
    menu.enum_items.clear()
    for i, name in enumerate(('Straight Grain', 'Growth Rings', 'Plywood')):
        menu.enum_items.new(name=name)
    for i in range(3):
        menu.inputs[i+1].default_value = i
    g.set(menu.inputs['Menu'], mode)
    index = menu.outputs[0]
    plywood = g.scalar('GREATER_THAN', index, 1.5)
    rings = g.scalar('GREATER_THAN', index, 0.5)
    light = g.input('Light Wood', (0.48, 0.25, 0.09, 1), 'Color')
    dark = g.input('Dark Wood', (0.15, 0.058, 0.018, 1), 'Color')
    units = g.input('Scene Unit m', bpy.context.scene.unit_settings.scale_length, limits=(0.000001, 1000))
    spacing = g.input('Ring Spacing mm', 2.5, limits=(0.1, 20))
    warp = g.input('Distortion mm', 5, limits=(0, 20))
    warp_size = g.input('Distortion Size mm', 25, limits=(1, 300))
    direction = g.input('Grain Rotation', (0, 0, 0), 'Vector')
    origin = g.input('Ring Center Offset mm', (0, 35, 12), 'Vector')
    rough = g.input('Roughness', 0.48, limits=(0.05, 1))
    pores = g.input('Pore Strength', 0.2, limits=(0, 1))
    relief = g.input('Relief mm', 0.015, limits=(0, 0.2))
    thickness = g.input('Ply Thickness mm', 1.5, limits=(0.1, 10))
    glue_width = g.input('Glue Width mm', 0.045, limits=(0, 0.5))
    veneer = g.input('Veneer Face', 0, limits=(0, 1))
    seed = g.input('Seed', 0, limits=(0, 1000))

    coord = g.node('ShaderNodeTexCoord', 'Local Coordinates')
    mm = g.vector('SCALE', coord.outputs['Object'], g.scalar('MULTIPLY', units, 1000), 'Coordinates mm')
    # Panel thickness stays on local Z independently of wood grain rotation.
    sep = g.node('ShaderNodeSeparateXYZ', 'Panel Coordinates')
    g.set(sep.inputs[0], mm)
    layer_position = g.scalar('DIVIDE', sep.outputs['Z'], thickness, 'Layer Position')
    layer = g.scalar('FLOOR', layer_position, name='Layer Index')
    parity = g.scalar('PINGPONG', layer, 1, 'Alternating Grain')
    quarter = g.scalar('MULTIPLY', parity, math.pi/2)
    rot = g.node('ShaderNodeVectorRotate', 'Alternate Veneer Direction')
    rot.rotation_type = 'Z_AXIS'
    g.set(rot.inputs['Vector'], mm)
    g.set(rot.inputs['Angle'], g.scalar('MULTIPLY', quarter, plywood))
    mapping = g.node('ShaderNodeMapping', 'Grain Orientation')
    g.set(mapping.inputs['Vector'], rot.outputs['Vector'])
    g.set(mapping.inputs['Rotation'], direction)
    shifted = g.vector('ADD', mapping.outputs['Vector'], origin)
    shifted = g.vector('ADD', shifted, g.vector('SCALE', (0.37, 0.61, 0.83), seed))
    stretched = g.vector('MULTIPLY', shifted, (0.5, 1, 1))
    distortion = g.noise(stretched, g.scalar('DIVIDE', 1, warp_size), 'Broad Grain Warp', True)
    distortion = g.vector('SUBTRACT', distortion, (0.5, 0.5, 0.5))
    warped = g.vector('ADD', shifted, g.vector('SCALE', distortion, warp))
    fine_warp = g.noise(g.vector('MULTIPLY', shifted, (0.08, 1, 1)), 0.25, 'Fine Grain Warp', True)
    fine_warp = g.vector('SUBTRACT', fine_warp, (0.5, 0.5, 0.5))
    warped = g.vector('ADD', warped, g.vector('SCALE', fine_warp, g.scalar('MULTIPLY', warp, 0.12)))
    # Blender wave phase is 20 * coordinate * Scale. One ring = 2*pi.
    frequency = g.scalar('DIVIDE', math.pi/10, spacing, 'Calibrated Ring Frequency')
    bands = g.wave(warped, frequency, 'Natural Wood Bands')
    circular = g.wave(warped, frequency, 'Growth Rings along X', 'RINGS', 'X')
    grain = g.mix(rings, bands, circular, 'Grain Pattern')
    latewood = g.node('ShaderNodeValToRGB', 'Narrow Latewood')
    latewood.color_ramp.elements[0].position = 0.7
    latewood.color_ramp.elements[1].position = 0.94
    g.set(latewood.inputs['Fac'], grain)
    wood = g.mix(latewood.outputs['Color'], light, dark, 'Earlywood and Latewood')
    fibers = g.noise(g.vector('MULTIPLY', shifted, (0.02, 4, 4)), 1, 'Long Fine Fibers')
    color = g.mix(g.scalar('MULTIPLY', fibers, 0.12), wood, dark, 'Fiber Color')

    even = g.wave(mm, g.scalar('DIVIDE', math.pi/20, thickness), 'Even Plywood Layers', axis='Z')
    even = g.scalar('GREATER_THAN', even, 0.5, 'Alternating Ply Tone')
    edge_mask = g.scalar('MULTIPLY', plywood, g.scalar('SUBTRACT', 1, veneer), 'Plywood Edge Mask')
    tone = g.mix(even, (0.55, 0.37, 0.18, 1), (0.32, 0.16, 0.055, 1), 'Ply Tones')
    ply_color = g.mix(0.22, tone, color, 'Grain within Veneers')
    fraction = g.scalar('FRACT', layer_position)
    boundary = g.scalar('MINIMUM', fraction, g.scalar('SUBTRACT', 1, fraction))
    glue = g.scalar('LESS_THAN', boundary, g.scalar('DIVIDE', glue_width, g.scalar('MULTIPLY', thickness, 2)), 'Glue Lines')
    ply_color = g.mix(glue, ply_color, (0.09, 0.047, 0.018, 1), 'Thin Glue Color')
    final_color = g.mix(edge_mask, color, ply_color, 'Wood or Plywood Edge')
    r = g.scalar('ADD', rough, g.scalar('MULTIPLY', g.scalar('SUBTRACT', fibers, 0.5), pores))
    r = g.scalar('MINIMUM', g.scalar('MAXIMUM', r, 0.02), 1, 'Bounded Roughness')
    bump = g.node('ShaderNodeBump', 'Shallow Fiber Relief')
    bump.inputs['Strength'].default_value = 0.25
    g.set(bump.inputs['Height'], fibers)
    g.set(bump.inputs['Distance'], g.scalar('DIVIDE', g.scalar('MULTIPLY', relief, 0.001), units))
    shader = g.node('ShaderNodeBsdfPrincipled', 'Sanded Wood')
    shader.inputs['Metallic'].default_value = 0
    g.set(shader.inputs['Base Color'], final_color)
    g.set(shader.inputs['Roughness'], r)
    g.set(shader.inputs['Normal'], bump.outputs['Normal'])
    g.output('Shader', shader.outputs['BSDF'], 'Shader')
    g.output('Layer Tone', even)
    g.output('Glue Mask', glue)
    g.output('Ring Pattern', bands)
    g.layout()
    return g.tree


def make_material(name='Procedural Wood', group=None, **settings):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    node = material.node_tree.nodes.new('ShaderNodeGroup')
    node.node_tree = group or build_group()
    node.name = 'Wood Controls'
    node.width = 310
    node.inputs['Structure'].default_value = 'Growth Rings'
    for key, value in settings.items():
        node.inputs[key].default_value = value
    out = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (430, 0)
    material.node_tree.links.new(node.outputs['Shader'], out.inputs['Surface'])
    return material


def preview(render):
    scene = bpy.data.scenes.new('Wood and Plywood Studio')
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    group = build_group()
    solid = make_material(group=group)
    straight = make_material('Straight Grain Wood', group, Structure='Straight Grain')
    edge = make_material('Plywood Edge', group, Structure='Plywood')
    veneer = make_material('Plywood Veneer', group, Structure='Straight Grain', **{
        'Light Wood': (0.62, 0.42, 0.2, 1), 'Dark Wood': (0.32, 0.17, 0.06, 1), 'Veneer Face': 1})
    def block(name, location, dimensions, materials):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for mat in materials:
            obj.data.materials.append(mat)
        if len(materials) > 1:
            # Ply interfaces start at the panel's lower face, local z = 0.
            for v in obj.data.vertices:
                v.co.z += dimensions[2]/2
            for face in obj.data.polygons:
                face.material_index = 1 if abs(face.normal.z) > 0.5 else 0
        bevel = obj.modifiers.new('Small Sanded Edge', 'BEVEL')
        bevel.width, bevel.segments = 0.0004, 3
        return obj
    body = block('Solid Wood 240mm', (0, 0.072, 0), (0.24, 0.07, 0.038), [solid])
    block('Straight Grain 240mm', (0, -0.025, 0), (0.24, 0.06, 0.026), [straight])
    block('Plywood 18mm', (0, -0.12, -0.009), (0.24, 0.08, 0.018), [edge, veneer])
    scene.world = bpy.data.worlds.new('Wood Studio World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.18, 0.2, 0.24, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.45
    for name, pos, energy, size in [('Key', (0.1,-0.3,0.45), 12,0.3), ('Fill',(-0.35,-0.1,0.15),6,0.25),('Rim',(0.1,0.3,0.3),10,0.25)]:
        obj = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()
        obj.data.energy, obj.data.shape, obj.data.size = energy, 'DISK', size
    camera = bpy.data.objects.new('Wood Camera', bpy.data.cameras.new('Wood Camera'))
    scene.collection.objects.link(camera)
    camera.location = (0.36,-0.52,0.4)
    camera.rotation_euler = (Vector((0,-0.02,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type, camera.data.ortho_scale, camera.data.clip_start = 'ORTHO', 0.44, 0.001
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.samples, scene.cycles.use_denoising = 64, True
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(DIRECTORY/'wood_preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    text = bpy.data.texts.get('wood.py') or bpy.data.texts.new('wood.py')
    text.clear()
    text.write(Path(__file__).read_text(encoding='utf-8'))
    text.filepath = str(Path(__file__).resolve())
    bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY/'wood.blend'))
    if render:
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
            raise RuntimeError('Select a mesh before running wood.py')
        material = make_material()
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = material
            else:
                obj.data.materials.append(material)


if __name__ == '__main__':
    main()
