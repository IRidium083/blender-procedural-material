"""Shared mask generation, shader-in/shader-out deposits, and clear-finish response.
Kept in one embedded source so appended files can be rebuilt without the repo.
"""
from pathlib import Path
import bpy

CONTROLS = [
    ('Coat Amount',.85,(0,1)),('Coat Roughness',.16,(.02,1)),
    ('Surface Scratches',.15,(0,1)),('Scratch Tile mm',45,(1,1000)),
    ('Scratch Relief mm',.002,(0,.05)),('Smudges',.18,(0,1)),
    ('Smudge Size mm',18,(.1,500)),('Surface Dust',.03,(0,1)),('Surface Seed',4,(0,1000)),
]
MARK_CONTROLS = ('Surface Scratches','Scratch Tile mm','Smudges','Smudge Size mm','Surface Seed')


class Builder:
    def __init__(self,name,key,version=1):
        self.tree = bpy.data.node_groups.new(name,'ShaderNodeTree')
        self.tree[key] = version
        self.gin = self.node('NodeGroupInput','Inputs')
        self.gout = self.node('NodeGroupOutput','Outputs')

    def node(self,kind,name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 200
        return n

    def set(self,target,value):
        if isinstance(value,bpy.types.NodeSocket):
            self.tree.links.new(value,target)
        else:
            target.default_value = value

    def input(self,name,value=0,kind='Float',limits=None):
        s = self.tree.interface.new_socket(name=name,in_out='INPUT',socket_type='NodeSocket'+kind)
        if kind != 'Shader':
            s.default_value = value
        if limits:
            s.min_value,s.max_value = limits
        return self.gin.outputs[name]

    def output(self,name,value,kind='Float'):
        self.tree.interface.new_socket(name=name,in_out='OUTPUT',socket_type='NodeSocket'+kind)
        self.set(self.gout.inputs[name],value)

    def calc(self,op,a,b=0,name=None,clamp=False):
        n = self.node('ShaderNodeMath',name or op)
        n.operation,n.use_clamp = op,clamp
        self.set(n.inputs[0],a)
        self.set(n.inputs[1],b)
        return n.outputs[0]

    def vector(self,op,a,b,name):
        n = self.node('ShaderNodeVectorMath',name)
        n.operation = op
        self.set(n.inputs[0],a)
        self.set(n.inputs['Scale'] if op == 'SCALE' else n.inputs[1],b)
        return n.outputs[0]

    def mix(self,f,a,b,name):
        n = self.node('ShaderNodeMixRGB',name)
        self.set(n.inputs[0],f)
        for i,v in enumerate((a,b),1):
            if isinstance(v,(int,float)):
                v = (v,v,v,1)
            self.set(n.inputs[i],v)
        return n.outputs[0]

    def group(self,name,tree):
        n = self.node('ShaderNodeGroup',name)
        n.node_tree = tree
        return n

    def finish(self):
        depths = {n:0 for n in self.tree.nodes}
        for _ in depths:
            changed = False
            for link in self.tree.links:
                d = depths[link.from_node]+1
                if d > depths[link.to_node]:
                    depths[link.to_node] = d
                    changed = True
            if not changed:
                break
        rows = {}
        for n,d in depths.items():
            row = rows.get(d,0)
            n.location = (d*280,-row*300)
            rows[d] = row+1
        return self.tree


def cached(name,key,version=1):
    tree = bpy.data.node_groups.get(name)
    return tree if tree and tree.get(key) == version else None


def build_patch_group():
    name,key = 'Shared - Surface Patch Field v1','surface_patch_version'
    existing = cached(name,key)
    if existing:
        return existing
    g = Builder(name,key)
    xyz = g.input('Coordinates mm',(0,0,0),'Vector')
    size = g.input('Patch Size mm',18,limits=(.1,500))
    seed = g.input('Seed',4,limits=(0,1000))
    shifted = g.vector('ADD',xyz,g.vector('SCALE',(1.37,2.19,.73),seed,'Seed Offset'),'Independent Surface Coordinates')
    noise = g.node('ShaderNodeTexNoise','Soft Surface Patches')
    g.set(noise.inputs['Vector'],shifted)
    g.set(noise.inputs['Scale'],g.calc('DIVIDE',1,size))
    noise.inputs['Detail'].default_value = 2
    patches = g.calc('MULTIPLY',g.calc('SUBTRACT',noise.outputs['Fac'],.35),3,'Patch Coverage',True)
    g.output('Patches',patches)
    g.output('Shifted Coordinates mm',shifted,'Vector')
    return g.finish()


def build_marks_group():
    name,key = 'Shared - Surface Marks v1','surface_marks_version'
    existing = cached(name,key)
    if existing:
        return existing
    g = Builder(name,key)
    xyz = g.input('Coordinates mm',(0,0,0),'Vector')
    controls = {n:g.input(n,v,limits=limits) for n,v,limits in CONTROLS if n in MARK_CONTROLS}
    patches = g.group('Shared Surface Patches',build_patch_group())
    for n,v in [('Coordinates mm',xyz),('Patch Size mm',controls['Smudge Size mm']),('Seed',controls['Surface Seed'])]:
        g.set(patches.inputs[n],v)
    image = bpy.data.images.get('Shared Clear Finish Scratches')
    if image is None or not image.packed_file:
        path = Path(__file__).resolve().parent/'textures'/'clear_finish_scratches.png'
        image = bpy.data.images.load(str(path),check_existing=True)
        image.name = 'Shared Clear Finish Scratches'
        image.colorspace_settings.name = 'Non-Color'
        image.pack()
        image.filepath = '//../shared/textures/clear_finish_scratches.png'
    texture = g.node('ShaderNodeTexImage','Shared Scratch Image')
    texture.image,texture.projection,texture.projection_blend = image,'BOX',.2
    texture.extension = 'REPEAT'
    g.set(texture.inputs['Vector'],g.vector('SCALE',patches.outputs['Shifted Coordinates mm'],g.calc('DIVIDE',1,controls['Scratch Tile mm']),'Scratch Image Tiling'))
    g.output('Scratch Mask',g.calc('MULTIPLY',texture.outputs['Color'],controls['Surface Scratches'],'Scratch Coverage'))
    g.output('Smudge Mask',g.calc('MULTIPLY',patches.outputs['Patches'],controls['Smudges'],'Smudge Coverage'))
    return g.finish()


def build_deposit_mask_group():
    name,key = 'Shared - Deposit Coverage v1','deposit_mask_version'
    existing = cached(name,key)
    if existing:
        return existing
    g = Builder(name,key)
    xyz = g.input('Coordinates mm',(0,0,0),'Vector')
    dust = g.input('Dust',0,limits=(0,1))
    size = g.input('Patch Size mm',18,limits=(.1,500))
    seed = g.input('Seed',4,limits=(0,1000))
    extra = g.input('Additional Coverage',0,limits=(0,1))
    patches = g.group('Shared Surface Patches',build_patch_group())
    for n,v in [('Coordinates mm',xyz),('Patch Size mm',size),('Seed',seed)]:
        g.set(patches.inputs[n],v)
    geometry = g.node('ShaderNodeNewGeometry','Deposit Geometry')
    normal = g.node('ShaderNodeSeparateXYZ','Upward Dust Bias')
    g.set(normal.inputs[0],geometry.outputs['Normal'])
    up = g.calc('MAXIMUM',normal.outputs['Z'],0)
    coverage = g.calc('MULTIPLY',g.calc('ADD',.15,g.calc('MULTIPLY',up,.85)),dust)
    coverage = g.calc('MULTIPLY',coverage,patches.outputs['Patches'],'Surface Dust Coverage',True)
    g.output('Dust Mask',g.calc('MAXIMUM',coverage,extra,'Combined Deposit Coverage',True))
    return g.finish()


def build_deposits_group():
    """Accept ANY final surface shader and mix an independent dust layer over it."""
    name,key = 'Shared - Surface Deposits v1','surface_deposits_version'
    existing = cached(name,key)
    if existing:
        return existing
    g = Builder(name,key)
    surface = g.input('Surface',kind='Shader')
    mask = g.group('Shared Deposit Coverage',build_deposit_mask_group())
    for n,v,kind,limits in [('Coordinates mm',(0,0,0),'Vector',None),('Dust',0,'Float',(0,1)),
                          ('Patch Size mm',18,'Float',(.1,500)),('Seed',4,'Float',(0,1000)),
                          ('Additional Coverage',0,'Float',(0,1))]:
        g.set(mask.inputs[n],g.input(n,v,kind,limits))
    color = g.input('Dust Color',(.24,.20,.14,1),'Color')
    normal = g.input('Dust Normal',(0,0,0),'Vector')
    # An unconnected zero vector uses the geometry normal; callers may supply bump.
    length = g.node('ShaderNodeVectorMath','Optional Normal Length')
    length.operation = 'LENGTH'
    g.set(length.inputs[0],normal)
    geometry = g.node('ShaderNodeNewGeometry','Deposit Surface Geometry')
    resolved_normal = g.mix(g.calc('LESS_THAN',length.outputs['Value'],.000001),normal,geometry.outputs['Normal'],'Deposit Normal')
    dust = g.node('ShaderNodeBsdfPrincipled','Nonmetallic Surface Deposit')
    g.set(dust.inputs['Base Color'],color)
    g.set(dust.inputs['Normal'],resolved_normal)
    dust.inputs['Metallic'].default_value = 0
    dust.inputs['Roughness'].default_value = .9
    blend = g.node('ShaderNodeMixShader','Deposits over Incoming Surface')
    g.set(blend.inputs[0],mask.outputs['Dust Mask'])
    g.set(blend.inputs[1],surface)
    g.set(blend.inputs[2],dust.outputs[0])
    g.output('Shader',blend.outputs[0],'Shader')
    g.output('Dust Mask',mask.outputs['Dust Mask'])
    return g.finish()


def build_group():
    """Wood/FRP clear-coat response, separate from final shader deposits."""
    name,key = 'Shared - Clear Finish Response v3','shared_finish_version'
    existing = cached(name,key,3)
    if existing:
        return existing
    g = Builder(name,key,3)
    xyz = g.input('Coordinates mm',(0,0,0),'Vector')
    units = g.input('Scene Unit m',1,limits=(.000001,1000))
    mode = g.input('Finish Index',1)
    controls = {n:g.input(n,v,limits=limits) for n,v,limits in CONTROLS if n != 'Surface Dust'}
    marks = g.group('Shared Surface Marks',build_marks_group())
    g.set(marks.inputs['Coordinates mm'],xyz)
    for n in MARK_CONTROLS:
        g.set(marks.inputs[n],controls[n])
    scratch,smudge = marks.outputs['Scratch Mask'],marks.outputs['Smudge Mask']
    enabled,wax = g.calc('GREATER_THAN',mode,.5),g.calc('GREATER_THAN',mode,1.5)
    weight = g.calc('MULTIPLY',g.calc('MULTIPLY',enabled,controls['Coat Amount']),g.mix(wax,1,.65,'Paint or Wax Weight'))
    base_rough = g.mix(wax,controls['Coat Roughness'],g.calc('MAXIMUM',controls['Coat Roughness'],.38),'Paint or Wax Roughness')
    rough = g.calc('ADD',base_rough,g.calc('ADD',g.calc('MULTIPLY',scratch,.35),g.calc('MULTIPLY',smudge,.22)),'Marked Coat Roughness',True)
    geometry = g.node('ShaderNodeNewGeometry','Uncoated Geometry')
    bump = g.node('ShaderNodeBump','Scratches in Top Finish')
    bump.invert = True
    bump.inputs['Strength'].default_value = .25
    g.set(bump.inputs['Normal'],geometry.outputs['Normal'])
    g.set(bump.inputs['Height'],scratch)
    g.set(bump.inputs['Distance'],g.calc('DIVIDE',g.calc('MULTIPLY',controls['Scratch Relief mm'],.001),units))
    for n,v in [('Coat Weight',weight),('Coat Roughness',rough),('Scratch Mask',scratch),('Smudge Mask',smudge)]:
        g.output(n,v)
    g.output('Coat Normal',bump.outputs['Normal'],'Vector')
    return g.finish()


def attach_finish(g,shader,coordinates_mm,units,defaults=None):
    defaults = defaults or {}
    mode = g.input('Clear Finish',None,'Menu')
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
    controls = {n:g.input(n,defaults.get(n,v),limits=limits) for n,v,limits in CONTROLS}
    for n,v in controls.items():
        if n != 'Surface Dust':
            g.set(finish.inputs[n],v)
    for n in ('Coat Weight','Coat Roughness','Coat Normal'):
        g.set(shader.inputs[n],finish.outputs[n])
    shader.inputs['Coat IOR'].default_value = 1.46
    shader.inputs['Coat Tint'].default_value = (1,1,1,1)
    deposits = g.node('ShaderNodeGroup','Shared Surface Deposits')
    deposits.node_tree = build_deposits_group()
    for n,v in [('Surface',shader.outputs['BSDF']),('Coordinates mm',coordinates_mm),('Dust',controls['Surface Dust']),
                ('Patch Size mm',controls['Smudge Size mm']),('Seed',controls['Surface Seed']),
                ('Dust Color',g.input('Surface Dust Color',(.24,.20,.14,1),'Color'))]:
        g.set(deposits.inputs[n],v)
    for n in ('Coat Weight','Coat Roughness','Scratch Mask','Smudge Mask'):
        g.output(n,finish.outputs[n])
    g.output('Dust Mask',deposits.outputs['Dust Mask'])
    return deposits.outputs['Shader']
