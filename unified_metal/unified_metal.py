"""Unified Metal v2, Blender 5.2. Separate finish families and shared imperfections.
Run with selected meshes, or CLI --preview --render. All surface sizes are mm.
Coatings, plating removal and substrate reveal are intentionally deferred.
"""
import argparse
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
    from shared.surface_finish import build_marks_group as shared_surface_group, build_deposit_mask_group, build_deposits_group
except ModuleNotFoundError:
    source = bpy.data.texts.get('shared_surface_finish.py')
    if source is None:
        raise RuntimeError('Keep shared/surface_finish.py beside the material folders.')
    namespace = {'__name__': 'shared_surface_finish'}
    exec(source.as_string(), namespace)
    shared_surface_group = namespace['build_marks_group']
    build_deposit_mask_group = namespace['build_deposit_mask_group']
    build_deposits_group = namespace['build_deposits_group']

VERSION = "2.0"
PREFIX = "UM v2 | "
IMAGE_NAME = "UM Oil Smears"
METALS = ["Steel", "Aluminum", "Bronze", "Copper"]
FINISHES = ["Polished", "Brushed", "Cast", "Stonewashed", "Machined", "Custom"]


def oil_image():
    image = bpy.data.images.get(IMAGE_NAME)
    if image and image.packed_file:
        return image
    relative = Path("textures/oil_smear_mask.png")
    candidates = [Path(__file__).resolve().parent / relative]
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).parent / relative)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError("Missing textures/oil_smear_mask.png; keep it beside unified_metal.py or use the packed .blend.")
    image = bpy.data.images.load(str(path), check_existing=True)
    image.name = IMAGE_NAME
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


class Graph:
    """Small builder; all module boundaries are ordinary shader-group sockets."""
    def __init__(self, name):
        self.tree = bpy.data.node_groups.new(PREFIX + name, "ShaderNodeTree")
        self.tree["um_version"] = VERSION
        self.specs = []
        self.gin = self.node("NodeGroupInput", "Inputs")
        self.gout = self.node("NodeGroupOutput", "Outputs")

    def node(self, kind, name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 210
        return n

    def set(self, target, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, target)
        else:
            target.default_value = value

    def input(self, name, kind="Float", default=None, limits=None, panel=None):
        s = self.tree.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocket" + kind)
        if default is not None and kind != "Menu":
            s.default_value = default
        if limits:
            s.min_value, s.max_value = limits
        if panel:
            self.tree.interface.move_to_parent(s, panel, len(panel.interface_items))
        self.specs.append((name, kind, default, limits))
        return self.gin.outputs[name]

    def output(self, name, value, kind="Float"):
        self.tree.interface.new_socket(name=name, in_out="OUTPUT", socket_type="NodeSocket" + kind)
        self.set(self.gout.inputs[name], value)

    def math(self, op, a, b=0, name=None, clamp=False):
        n = self.node("ShaderNodeMath", name or op.title())
        n.operation, n.use_clamp = op, clamp
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        if op == "COMPARE":
            n.inputs[2].default_value = 0.1
        return n.outputs[0]

    def vector(self, op, a, b):
        n = self.node("ShaderNodeVectorMath", op.title())
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs["Scale"] if op == "SCALE" else n.inputs[1], b)
        return n.outputs[0]

    def mix(self, factor, a, b, name="Blend"):
        n = self.node("ShaderNodeMixRGB", name)
        self.set(n.inputs[0], factor)
        for i, value in enumerate((a, b), 1):
            if isinstance(value, (int, float)):
                value = (value, value, value, 1)
            elif isinstance(value, tuple) and len(value) == 3:
                value = (*value, 1)
            self.set(n.inputs[i], value)
        return n.outputs[0]

    def menu(self, socket, names, values=None, kind="INT"):
        n = self.node("GeometryNodeMenuSwitch", socket.name + " Presets")
        n.data_type = kind
        n.enum_items.clear()
        for name in names:
            n.enum_items.new(name=name)
        self.set(n.inputs["Menu"], socket)
        for i, value in enumerate(values if values is not None else range(len(names))):
            self.set(n.inputs[i + 1], value)
        return n.outputs[0]

    def pick(self, index, values, name):
        # Index Switch is not registered for ShaderNodeTree in the installed 5.2.
        # Resolve scalar preset channels with exact integer comparisons instead.
        terms = [self.math("MULTIPLY", self.math("COMPARE", index, i), v)
                 for i, v in enumerate(values)]
        result = terms[0]
        for term in terms[1:]:
            result = self.math("ADD", result, term, name)
        return result

    def noise(self, coords, scale, detail=2, name="Noise"):
        n = self.node("ShaderNodeTexNoise", name)
        self.set(n.inputs["Vector"], coords)
        self.set(n.inputs["Scale"], scale)
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = 0.65
        return n.outputs["Fac"]

    def ramp(self, value, low, high, name):
        n = self.node("ShaderNodeValToRGB", name)
        n.color_ramp.elements[0].position = low
        n.color_ramp.elements[1].position = high
        self.set(n.inputs["Fac"], value)
        return n.outputs["Color"]

    def instance(self, module):
        n = self.node("ShaderNodeGroup", module.tree.name)
        n.node_tree = module.tree
        n.width = 280
        return n

    def layout(self):
        depth = {n: 0 for n in self.tree.nodes}
        for _ in range(len(depth)):
            changed = False
            for edge in self.tree.links:
                d = depth[edge.from_node] + 1
                if depth[edge.to_node] < d:
                    depth[edge.to_node], changed = d, True
            if not changed:
                break
        rows = {}
        for n, d in depth.items():
            row = rows.get(d, 0)
            n.location = (d * 320, -row * 360)
            rows[d] = row + 1


def base_module():
    g = Graph("Base Metal")
    metal = g.input("Base Metal", "Menu")
    color = g.menu(metal, METALS, [
        (0.55, 0.58, 0.6, 1), (0.83, 0.85, 0.88, 1),
        (0.55, 0.32, 0.12, 1), (0.90, 0.47, 0.28, 1)], "RGBA")
    g.output("Color", color, "Color")
    return g


# roughness, physical grain size mm, shallow relief mm, anisotropy
FINISH_DEFAULTS = {
    'Polished': (.12, .5, .0005, 0),
    'Brushed': (.32, .5, .003, .65),
    'Cast': (.68, .5, .025, 0),
    'Stonewashed': (.48, .5, .009, .15),
    'Machined': (.22, .5, 0, .4),
    'Custom': (.35, .5, .008, 0),
}


def finish_module(family):
    """Build only the selected manufacturing process, with no finish switch."""
    g = Graph(family + " Structure")
    g.tree['finish_family'] = family
    roughness, size, depth, anis = FINISH_DEFAULTS[family]
    xyz = g.input('Coordinates mm', 'Vector', (0,0,0))
    rough = g.input('Roughness', default=roughness, limits=(.02,1))
    grain = g.input('Grain mm', default=size, limits=(.01,10))
    detail = g.input('Surface Detail', default=1, limits=(0,2))
    relief = g.input('Relief mm', default=depth, limits=(0,.5))
    anisotropy = g.input('Anisotropy', default=anis, limits=(0,1))
    direction = g.input('Direction', 'Vector', (0,0,0))
    seed = g.input('Finish Seed', default=0, limits=(0,1000))
    mapping = g.node('ShaderNodeMapping','Finish Orientation')
    g.set(mapping.inputs['Vector'],xyz)
    g.set(mapping.inputs['Rotation'],direction)
    v = g.vector('SCALE',mapping.outputs['Vector'],g.math('DIVIDE',1,grain))
    v = g.vector('ADD',v,g.vector('SCALE',(0.37,.61,.83),seed))
    if family == 'Brushed':
        pattern = g.noise(g.vector('MULTIPLY',v,(.03,3,3)),1,2,'Straight Brush Lines')
    elif family == 'Machined':
        pattern = g.noise(g.vector('MULTIPLY',v,(.02,.02,5)),1,2,'Shallow Turning Bands')
    elif family == 'Stonewashed':
        pattern = g.math('POWER',g.noise(v,1.7,3,'Stonewash Dents'),2)
    else:
        pattern = g.noise(v,1,4,family+' Grain')
    variation = g.math('MULTIPLY',g.math('SUBTRACT',pattern,.5),detail)
    new_rough = g.math('ADD',rough,g.math('MULTIPLY',variation,.1),clamp=True)
    height = 0 if family == 'Machined' else g.math('MULTIPLY',pattern,g.math('MULTIPLY',relief,detail))
    color_factor = g.math('SUBTRACT',1,g.math('MULTIPLY',g.math('MULTIPLY',pattern,detail),.08)) if family == 'Machined' else 1
    if family == 'Machined':
        anisotropy = g.math('ADD',anisotropy,g.math('MULTIPLY',variation,.25),clamp=True)
    # Coordinate rotation is inverted as a full Euler transform, then transformed
    # into world space and projected onto the shading surface.
    tangent = g.node('ShaderNodeVectorRotate','Inverse Finish Direction')
    tangent.rotation_type, tangent.invert = 'EULER_XYZ', True
    g.set(tangent.inputs['Rotation'],direction)
    local = (1,0,0)
    if family == 'Machined':
        radial = g.vector('CROSS_PRODUCT',(0,0,1),mapping.outputs['Vector'])
        length = g.node('ShaderNodeVectorMath','Radial Tangent Length')
        length.operation = 'LENGTH'
        g.set(length.inputs[0],radial)
        local = g.mix(g.math('LESS_THAN',length.outputs['Value'],.000001),radial,(1,0,0),'Turning Axis Fallback')
    g.set(tangent.inputs['Vector'],local)
    world = g.node('ShaderNodeVectorTransform','World Finish Direction')
    world.vector_type, world.convert_from, world.convert_to = 'VECTOR','OBJECT','WORLD'
    g.set(world.inputs['Vector'],tangent.outputs['Vector'])
    geometry = g.node('ShaderNodeNewGeometry','Finish Geometry')
    normal = geometry.outputs['Normal']
    projected = g.vector('CROSS_PRODUCT',g.vector('CROSS_PRODUCT',normal,world.outputs[0]),normal)
    length = g.node('ShaderNodeVectorMath','Projected Tangent Length')
    length.operation = 'LENGTH'
    g.set(length.inputs[0],projected)
    normal_z = g.node('ShaderNodeSeparateXYZ','Surface Normal Components')
    g.set(normal_z.inputs[0],normal)
    axis = g.mix(g.math('GREATER_THAN',g.math('ABSOLUTE',normal_z.outputs['Z']),.9),(0,0,1),(1,0,0),'Stable Fallback Axis')
    fallback = g.vector('CROSS_PRODUCT',normal,axis)
    projected = g.mix(g.math('LESS_THAN',length.outputs['Value'],.000001),projected,fallback,'Surface Tangent')
    g.output('Roughness',new_rough)
    g.output('Height mm',height)
    g.output('Anisotropy',anisotropy)
    g.output('Color Factor',color_factor)
    g.output('Tangent',g.vector('NORMALIZE',projected,(0,0,0)),'Vector')
    return g


def imperfections_module(image):
    """Shared masks from wood/FRP, plus metal-specific edge polish and oil."""
    g = Graph('Metal Imperfections')
    xyz = g.input('Coordinates mm','Vector',(0,0,0))
    units = g.input('Scene Unit m',default=1,limits=(.000001,1000))
    rough = g.input('Roughness',default=.3)
    height = g.input('Height mm',default=0)
    wear = g.input('Edge Wear',default=.2,limits=(0,1))
    width = g.input('Wear Width mm',default=.6,limits=(.01,20))
    surface_wear = g.input('Surface Wear',default=.15,limits=(0,1))
    tile = g.input('Scratch Tile mm',default=45,limits=(1,1000))
    scratch_depth = g.input('Scratch Depth mm',default=.003,limits=(0,.1))
    dust_amount = g.input('Dust',default=0,limits=(0,1))
    dust_color = g.input('Dust Color','Color',(.22,.17,.1,1))
    dust_distance = g.input('Dust Spread mm',default=3,limits=(.01,100))
    oil_amount = g.input('Oil',default=0,limits=(0,1))
    oil_size = g.input('Oil Patch mm',default=30,limits=(.1,500))
    oil_tint = g.input('Oil Tint','Color',(.13,.075,.025,1))
    seed = g.input('Imperfection Seed',default=7,limits=(0,1000))
    shared = g.node('ShaderNodeGroup','Shared Surface Imperfections')
    shared.node_tree = shared_surface_group()
    for name,value in [('Coordinates mm',xyz),('Surface Scratches',surface_wear),
                       ('Scratch Tile mm',tile),('Smudges',g.math('MULTIPLY',surface_wear,1.2,clamp=True)),
                       ('Surface Seed',seed)]:
        g.set(shared.inputs[name],value)
    scratch, smudge = shared.outputs['Scratch Mask'], shared.outputs['Smudge Mask']
    mm_to_units = g.math('DIVIDE',.001,units)
    shifted = g.vector('ADD',xyz,g.vector('SCALE',(1.3,2.7,.9),seed))
    breakup = g.noise(shifted,.4,3,'Wear Distribution')
    geometry = g.node('ShaderNodeNewGeometry','Unbumped Geometry')
    def ao(inside,distance,title):
        n = g.node('ShaderNodeAmbientOcclusion',title)
        n.inside,n.samples = inside,16
        g.set(n.inputs['Normal'],geometry.outputs['Normal'])
        g.set(n.inputs['Distance'],g.math('MULTIPLY',distance,mm_to_units))
        return g.math('SUBTRACT',1,n.outputs['AO'])
    edge = g.math('MULTIPLY',g.math('MULTIPLY',ao(True,width,'Convex Edge Wear'),4,clamp=True),breakup)
    edge = g.math('MULTIPLY',edge,wear)
    new_height = g.math('MULTIPLY',height,g.math('SUBTRACT',1,edge))
    new_height = g.math('SUBTRACT',new_height,g.math('MULTIPLY',scratch,scratch_depth))
    marks_rough = g.math('ADD',g.math('MULTIPLY',scratch,.15),g.math('MULTIPLY',smudge,.12))
    new_rough = g.math('ADD',g.math('SUBTRACT',rough,g.math('MULTIPLY',edge,.25)),marks_rough,clamp=True)
    # Shared upward dust plus geometry-dependent cavity accumulation for metal.
    cavity = g.math('MULTIPLY',ao(False,dust_distance,'Cavity Deposit Mask'),2.8,clamp=True)
    cavity = g.math('MULTIPLY',cavity,g.math('MULTIPLY',dust_amount,breakup))
    coverage = g.node('ShaderNodeGroup','Shared Deposit Coverage')
    coverage.node_tree = build_deposit_mask_group()
    for name,value in [('Coordinates mm',xyz),('Dust',dust_amount),('Seed',seed),('Additional Coverage',cavity)]:
        g.set(coverage.inputs[name],value)
    dust = coverage.outputs['Dust Mask']
    tex = g.node('ShaderNodeTexImage','Oil Smears')
    tex.image,tex.projection,tex.projection_blend = image,'BOX',.3
    tex.extension = 'REPEAT'
    g.set(tex.inputs['Vector'],g.vector('SCALE',shifted,g.math('DIVIDE',1,oil_size)))
    oil = g.math('MULTIPLY',g.ramp(tex.outputs['Color'],.065,.48,'Oil Residue Mask'),oil_amount)
    for name,value in [('Roughness',new_rough),('Height mm',new_height),('Wear Mask',edge),
                       ('Scratch Mask',scratch),('Smudge Mask',smudge),('Dust Mask',dust),('Oil Mask',oil)]:
        g.output(name,value)
    g.output('Dust Color',dust_color,'Color')
    g.output('Oil Tint',oil_tint,'Color')
    return g


def build_library(family='Polished', base=None, imperfections=None):
    base = base or base_module()
    imperfections = imperfections or imperfections_module(oil_image())
    finish = finish_module(family)
    g = Graph(family+' Metal Core')
    g.tree['finish_family'] = family
    f,imp = g.instance(finish),g.instance(imperfections)
    f.name,imp.name = 'Finish Structure','Metal Imperfections'
    if family == 'Custom':
        color = g.input('Metal Color','Color',(.55,.58,.6,1))
    else:
        b = g.instance(base)
        b.name = 'Base Metal'
        g.set(b.inputs['Base Metal'],g.input('Base Metal','Menu'))
        tint = g.node('ShaderNodeMixRGB','Metal Color Tint')
        tint.blend_type = 'MULTIPLY'
        tint.inputs[0].default_value = 1
        g.set(tint.inputs[1],b.outputs['Color'])
        g.set(tint.inputs[2],g.input('Color Tint','Color',(1,1,1,1)))
        color = tint.outputs[0]
    internal = {'Coordinates mm','Scene Unit m','Height mm'}
    for module,instance in [(finish,f),(imperfections,imp)]:
        for name,kind,value,limits in module.specs:
            if name not in internal and not (module == imperfections and name == 'Roughness'):
                g.set(instance.inputs[name],g.input(name,kind,value,limits))
    units = g.input('Scene Unit m',default=bpy.context.scene.unit_settings.scale_length,limits=(.000001,1000))
    coords = g.node('ShaderNodeTexCoord','Shared Object Coordinates')
    xyz = g.vector('SCALE',coords.outputs['Object'],g.math('MULTIPLY',units,1000))
    xyz.node.name = 'Coordinates mm'
    for target in (f,imp):
        g.set(target.inputs['Coordinates mm'],xyz)
    g.set(imp.inputs['Scene Unit m'],units)
    for name in ('Roughness','Height mm'):
        g.set(imp.inputs[name],f.outputs[name])
    bump = g.node('ShaderNodeBump','Combined Surface Relief')
    g.set(bump.inputs['Height'],imp.outputs['Height mm'])
    g.set(bump.inputs['Distance'],g.math('DIVIDE',.001,units))
    bump.inputs['Strength'].default_value = .5
    color = g.vector('SCALE',color,f.outputs['Color Factor'])
    color = g.mix(imp.outputs['Oil Mask'],color,imp.outputs['Oil Tint'],'Oil Stains')
    rough = g.mix(imp.outputs['Oil Mask'],imp.outputs['Roughness'],.24,'Oil Smear Roughness')
    metal = g.node('ShaderNodeBsdfPrincipled','Finished Metal')
    for name,value in [('Base Color',color),('Metallic',1),('Roughness',rough),('Normal',bump.outputs['Normal']),
                       ('Anisotropic',f.outputs['Anisotropy']),('Tangent',f.outputs['Tangent']),('Coat Weight',imp.outputs['Oil Mask'])]:
        g.set(metal.inputs[name],value)
    metal.inputs['Coat Roughness'].default_value = .12
    deposits = g.node('ShaderNodeGroup','Shared Surface Deposits')
    deposits.node_tree = build_deposits_group()
    for name,value in [('Surface',metal.outputs[0]),('Coordinates mm',xyz),
                       ('Additional Coverage',imp.outputs['Dust Mask']),('Dust Color',imp.outputs['Dust Color']),
                       ('Dust Normal',bump.outputs['Normal'])]:
        g.set(deposits.inputs[name],value)
    g.output('Shader',deposits.outputs['Shader'],'Shader')
    for channel in ('Roughness','Height mm','Wear Mask','Scratch Mask','Smudge Mask','Dust Mask','Oil Mask'):
        g.output(channel,imp.outputs[channel])
    g.output('Base Color',color,'Color')
    g.output('Anisotropy',f.outputs['Anisotropy'])
    for module in (base,finish,imperfections,g):
        module.layout()
    return g.tree


def simple_group(core,family):
    if family == 'Custom':
        return core
    g = Graph(family+' Metal Controls')
    inner = g.node('ShaderNodeGroup','Advanced Metal Settings')
    inner.node_tree = core
    public = ['Base Metal','Color Tint','Roughness']
    if family != 'Polished':
        public.append('Grain Scale')
    if family in ('Brushed','Machined'):
        public.append('Direction')
    if family in ('Cast','Stonewashed','Machined'):
        public.append('Surface Detail')
    public += ['Edge Wear','Surface Wear','Dust','Oil']
    for name in public:
        if name == 'Grain Scale':
            value = g.input(name,default=1,limits=(.1,10))
            g.set(inner.inputs['Grain mm'],g.math('MULTIPLY',value,FINISH_DEFAULTS[family][1]))
            continue
        socket = next(s for s in core.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name == name)
        kind = socket.socket_type.removeprefix('NodeSocket')
        value = None if kind == 'Menu' else socket.default_value
        limits = (socket.min_value,socket.max_value) if kind == 'Float' else None
        g.set(inner.inputs[name],g.input(name,kind,value,limits))
    for socket in g.tree.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT':
            if socket.name == 'Direction':
                socket.subtype = 'EULER'
            socket.description = {
                'Grain Scale':'Finish pattern size multiplier; independent of scratches, oil and edge wear.',
                'Surface Detail':'Strength of finish variation; machining marks affect color, roughness and anisotropy only.',
                'Edge Wear':'Convex-edge polishing amount. Zero disables edge wear.',
                'Surface Wear':'Combined shared image scratches and handling smudges. Zero disables both.',
                'Dust':'Shared surface dust plus cavity deposits. Zero disables dust.',
                'Oil':'Image-based lubricant film and stains. Zero disables oil.',
            }.get(socket.name,'')
    g.output('Shader',inner.outputs['Shader'],'Shader')
    g.tree['finish_family'] = family
    g.layout()
    return g.tree


def make_material(name='UM Polished Metal', library=None, family='Polished', **settings):
    library = library or simple_group(build_library(family),family)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes,mat.use_fake_user = True,True
    if mat.asset_data:
        mat.asset_clear()
    mat.node_tree.nodes.clear()
    n = mat.node_tree.nodes.new('ShaderNodeGroup')
    n.node_tree,n.name,n.width = library,'Metal Controls',310
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (430,0)
    mat.node_tree.links.new(n.outputs['Shader'],out.inputs['Surface'])
    if 'Base Metal' in n.inputs:
        n.inputs['Base Metal'].default_value = 'Steel'
    for key,value in settings.items():
        n.inputs[key].default_value = value
    mat['um_version'],mat['finish_family'] = VERSION,family
    return mat


def preview(directory, render):
    scene = bpy.data.scenes.new("Unified Metal - Preset Gallery")
    bpy.context.window.scene = scene
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1
    base, imperfections = base_module(), imperfections_module(oil_image())
    libraries = {family:simple_group(build_library(family,base,imperfections),family) for family in FINISHES}
    samples = [
        ('Steel - Polished','Polished',{'Base Metal':'Steel','Edge Wear':0,'Surface Wear':0}),
        ('Aluminum - Brushed','Brushed',{'Base Metal':'Aluminum'}),
        ('Bronze - Cast','Cast',{'Base Metal':'Bronze','Dust':.55}),
        ('Copper - Stonewashed','Stonewashed',{'Base Metal':'Copper','Edge Wear':.5}),
        ('Steel - Machined + Oil','Machined',{'Base Metal':'Steel','Oil':.85}),
        ('Custom - Dust + Oil','Custom',{'Metal Color':(.4,.44,.48,1),'Roughness':.4,'Relief mm':.02,
                                       'Dust':.65,'Oil':.5,'Edge Wear':.6}),
    ]
    textmat = bpy.data.materials.new("UM Preview Labels")
    textmat.use_nodes = True
    textmat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.75, 0.8, 0.85, 1)
    bodies = []
    for i, (name, family, settings) in enumerate(samples):
        x, y = (i % 3 - 1) * 0.07, (0.5 - i // 3) * 0.12
        mat = make_material("UM " + family + " Metal", libraries[family], family, **settings)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0))
        body = bpy.context.object
        body.name, body.dimensions = name, (0.048, 0.044, 0.036)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y - 0.018, 0.001))
        cutter = bpy.context.object
        cutter.dimensions = (0.027, 0.018, 0.017)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.context.view_layer.objects.active = body
        boolean = body.modifiers.new("Recess", "BOOLEAN")
        boolean.operation, boolean.object = "DIFFERENCE", cutter
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        bevel = body.modifiers.new("Machined Corners", "BEVEL")
        bevel.width, bevel.segments = 0.001, 3
        # Boolean evaluation can create an empty slot: replace it explicitly.
        body.data.materials.clear()
        body.data.materials.append(mat)
        for polygon in body.data.polygons:
            polygon.material_index = 0
        bodies.append(body)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.011, location=(x, y, 0.019))
        cap = bpy.context.object
        cap.name = name + " Curved Sample"
        cap.data.materials.append(mat)
        for poly in cap.data.polygons:
            poly.use_smooth = True
        data = bpy.data.curves.new(name + " Label", "FONT")
        data.body, data.align_x, data.size = name, "CENTER", 0.0032
        obj = bpy.data.objects.new(name + " Label", data)
        scene.collection.objects.link(obj)
        obj.location = (x, y - 0.042, -0.017)
        obj.data.materials.append(textmat)
    world = bpy.data.worlds.new("UM Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.12, 0.16, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, location, power, size in [("Key", (-0.13, -0.15, 0.24), 2.4, 0.2),
                                       ("Fill", (0.16, -0.04, 0.15), 1.6, 0.16), ("Rim", (0, 0.2, 0.2), 2.5, 0.18)]:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.shape, data.size = power, "DISK", size
    camera = bpy.data.objects.new("Gallery Camera", bpy.data.cameras.new("Gallery Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (0.055, -0.3, 0.29)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale, camera.data.clip_start = "ORTHO", 0.30, 0.001
    configure_cycles(scene)
    scene.cycles.samples, scene.cycles.use_denoising = 48, True
    scene.render.resolution_x, scene.render.resolution_y = 1500, 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "unified_metal_preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    bodies[0].select_set(True)
    bpy.context.view_layer.objects.active = bodies[0]
    bpy.data.images[IMAGE_NAME].filepath = "//textures/oil_smear_mask.png"
    bpy.data.texts.load(str(directory / "unified_metal.py"))
    shared_path = directory.parent/'shared'/'surface_finish.py'
    shared_text = bpy.data.texts.get('shared_surface_finish.py') or bpy.data.texts.new('shared_surface_finish.py')
    if shared_path.exists():
        shared_text.clear()
        shared_text.write(shared_path.read_text(encoding='utf-8'))
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "unified_metal.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.preview:
        preview(Path(__file__).resolve().parent, args.render)
    else:
        meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not meshes:
            raise RuntimeError("Select a mesh before running the generator.")
        mat = make_material()
        for obj in meshes:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
    print("Unified Metal v2 created in Blender", bpy.app.version_string)


if __name__ == "__main__":
    main()
