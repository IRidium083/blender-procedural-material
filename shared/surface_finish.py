"""Substrate-independent clear finish and top-surface imperfections.

attach_finish accepts the small Graph interface used by wood and glassfiber:
node, input, output, set, and tree. Coordinates are millimeters; normals are world.
"""
from pathlib import Path
import bpy

NAME = 'Shared - Clear Finish and Surface Imperfections v2'
CONTROLS = [
    ('Coat Amount', 0.85, (0, 1)),
    ('Coat Roughness', 0.16, (0.02, 1)),
    ('Surface Scratches', 0.15, (0, 1)),
    ('Scratch Tile mm', 45, (1, 1000)),
    ('Scratch Relief mm', 0.002, (0, 0.05)),
    ('Smudges', 0.18, (0, 1)),
    ('Smudge Size mm', 18, (0.1, 500)),
    ('Surface Dust', 0.03, (0, 1)),
    ('Surface Seed', 4, (0, 1000)),
]


def build_group():
    existing = bpy.data.node_groups.get(NAME)
    if existing and existing.get('shared_finish_version') == 2:
        return existing
    tree = bpy.data.node_groups.new(NAME, 'ShaderNodeTree')
    tree['shared_finish_version'] = 2
    def node(kind, name):
        n = tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 190
        return n
    def set_(socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    inp, out = node('NodeGroupInput', 'Inputs'), node('NodeGroupOutput', 'Outputs')
    def input_(name, kind, value):
        s = tree.interface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocket'+kind)
        s.default_value = value
        return inp.outputs[name]
    xyz = input_('Coordinates mm', 'Vector', (0,0,0))
    units = input_('Scene Unit m', 'Float', 1)
    mode = input_('Finish Index', 'Float', 1)
    for name, value, limits in CONTROLS:
        input_(name, 'Float', value)
    def calc(op, a, b=0, name=None, clamp=False):
        n = node('ShaderNodeMath', name or op)
        n.operation, n.use_clamp = op, clamp
        set_(n.inputs[0], a)
        set_(n.inputs[1], b)
        return n.outputs[0]
    def vector(op, a, b, name):
        n = node('ShaderNodeVectorMath', name)
        n.operation = op
        set_(n.inputs[0], a)
        set_(n.inputs['Scale'] if op == 'SCALE' else n.inputs[1], b)
        return n.outputs[0]
    def noise(coords, scale, name):
        n = node('ShaderNodeTexNoise', name)
        set_(n.inputs['Vector'], coords)
        set_(n.inputs['Scale'], scale)
        n.inputs['Detail'].default_value = 2
        return n.outputs['Fac']
    def mix(f, a, b, name):
        n = node('ShaderNodeMixRGB', name)
        set_(n.inputs[0], f)
        for i, val in enumerate((a,b),1):
            if isinstance(val,(int,float)):
                val = (val,val,val,1)
            set_(n.inputs[i], val)
        return n.outputs[0]
    def output(name, value, kind='Float'):
        tree.interface.new_socket(name=name, in_out='OUTPUT', socket_type='NodeSocket'+kind)
        set_(out.inputs[name], value)
    controls = inp.outputs
    shifted = vector('ADD', xyz, vector('SCALE', (1.37,2.19,0.73), controls['Surface Seed'], 'Seed Offset'), 'Independent Surface Coordinates')
    image = bpy.data.images.get('Shared Clear Finish Scratches')
    if image is None or not image.packed_file:
        path = Path(__file__).resolve().parent/'textures'/'clear_finish_scratches.png'
        image = bpy.data.images.load(str(path), check_existing=True)
        image.name = 'Shared Clear Finish Scratches'
        image.colorspace_settings.name = 'Non-Color'
        image.pack()
        image.filepath = '//../shared/textures/clear_finish_scratches.png'
    texture = node('ShaderNodeTexImage','Shared Scratch Image')
    texture.image = image
    texture.projection = 'BOX'
    texture.projection_blend = 0.2
    texture.extension = 'REPEAT'
    set_(texture.inputs['Vector'],vector('SCALE',shifted,calc('DIVIDE',1,controls['Scratch Tile mm']),'Scratch Image Tiling'))
    scratches = calc('MULTIPLY',texture.outputs['Color'],controls['Surface Scratches'], 'Scratch Coverage')
    patches = noise(shifted, calc('DIVIDE',1,controls['Smudge Size mm']), 'Soft Handling Smudges')
    patches = calc('MULTIPLY',calc('SUBTRACT',patches,0.35),3, 'Smudge Patches',True)
    smudges = calc('MULTIPLY',patches,controls['Smudges'], 'Smudge Coverage')
    geometry = node('ShaderNodeNewGeometry', 'Uncoated Geometry')
    normal = node('ShaderNodeSeparateXYZ', 'Upward Dust Bias')
    set_(normal.inputs[0],geometry.outputs['Normal'])
    up = calc('MAXIMUM',normal.outputs['Z'],0)
    dust = calc('MULTIPLY',calc('ADD',0.15,calc('MULTIPLY',up,0.85)),controls['Surface Dust'])
    dust = calc('MULTIPLY',dust,patches,'Dust Coverage',True)
    enabled = calc('GREATER_THAN',mode,0.5)
    wax = calc('GREATER_THAN',mode,1.5)
    weight = calc('MULTIPLY',calc('MULTIPLY',enabled,controls['Coat Amount']),mix(wax,1,0.65,'Paint or Wax Weight'))
    base_rough = mix(wax,controls['Coat Roughness'],calc('MAXIMUM',controls['Coat Roughness'],0.38),'Paint or Wax Roughness')
    damage_rough = calc('ADD',calc('MULTIPLY',scratches,0.35),calc('MULTIPLY',smudges,0.22))
    rough = calc('ADD',base_rough,damage_rough,'Marked Coat Roughness',True)
    bump = node('ShaderNodeBump','Scratches in Top Finish')
    bump.invert = True
    bump.inputs['Strength'].default_value = 0.25
    set_(bump.inputs['Normal'],geometry.outputs['Normal'])
    set_(bump.inputs['Height'],scratches)
    set_(bump.inputs['Distance'],calc('DIVIDE',calc('MULTIPLY',controls['Scratch Relief mm'],0.001),units))
    output('Coat Weight',weight)
    output('Coat Roughness',rough)
    output('Coat Normal',bump.outputs['Normal'],'Vector')
    output('Scratch Mask',scratches)
    output('Smudge Mask',smudges)
    output('Dust Mask',dust)
    depths = {n:0 for n in tree.nodes}
    for _ in depths:
        for link in tree.links:
            depths[link.to_node] = max(depths[link.to_node],depths[link.from_node]+1)
    rows = {}
    for n,d in depths.items():
        row = rows.get(d,0)
        n.location = (d*275,-row*300)
        rows[d] = row+1
    return tree


def attach_finish(g, shader, coordinates_mm, units, defaults=None):
    """Layer finish on an existing Principled; return shader with dust above it."""
    defaults = defaults or {}
    mode = g.input('Clear Finish', None, 'Menu')
    menu = g.node('GeometryNodeMenuSwitch','Clear Finish Presets')
    menu.data_type = 'INT'
    menu.enum_items.clear()
    for name in ('None','Clear Paint','Wax'):
        menu.enum_items.new(name=name)
    for i in range(3):
        menu.inputs[i+1].default_value = i
    g.set(menu.inputs['Menu'],mode)
    finish = g.node('ShaderNodeGroup','Shared Surface Finish')
    finish.node_tree = build_group()
    g.set(finish.inputs['Coordinates mm'],coordinates_mm)
    g.set(finish.inputs['Scene Unit m'],units)
    g.set(finish.inputs['Finish Index'],menu.outputs[0])
    for name,value,limits in CONTROLS:
        g.set(finish.inputs[name],g.input(name,defaults.get(name,value),limits=limits))
    for name in ('Coat Weight','Coat Roughness','Coat Normal'):
        g.set(shader.inputs[name],finish.outputs[name])
    shader.inputs['Coat IOR'].default_value = 1.46
    shader.inputs['Coat Tint'].default_value = (1,1,1,1)
    dust = g.node('ShaderNodeBsdfPrincipled','Dust above Clear Finish')
    dust.inputs['Roughness'].default_value = 0.9
    dust.inputs['Metallic'].default_value = 0
    g.set(dust.inputs['Base Color'],g.input('Surface Dust Color',(0.24,0.20,0.14,1),'Color'))
    blend = g.node('ShaderNodeMixShader','Dust over Finished Surface')
    g.set(blend.inputs[0],finish.outputs['Dust Mask'])
    g.set(blend.inputs[1],shader.outputs['BSDF'])
    g.set(blend.inputs[2],dust.outputs['BSDF'])
    for channel in ('Coat Weight','Coat Roughness','Scratch Mask','Smudge Mask','Dust Mask'):
        g.output(channel,finish.outputs[channel])
    return blend.outputs[0]
