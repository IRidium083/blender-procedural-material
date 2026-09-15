"""Pure procedural molded-resin shading, shared by the Bakelite pattern families.
The caller supplies its Graph class (node/input/output/set/math/mix/noise/layout).
"""
import bpy
try:
    from shared.surface_finish import build_deposits_group
except ModuleNotFoundError:
    source = bpy.data.texts.get('shared_surface_finish.py')
    if source is None:
        raise RuntimeError('Keep shared/surface_finish.py beside resin_finish.py.')
    namespace = {'__name__':'shared_surface_finish'}
    exec(source.as_string(),namespace)
    build_deposits_group = namespace['build_deposits_group']

NAME = 'Shared - Molded Resin Surface v2'


def build_group(Graph):
    existing = bpy.data.node_groups.get(NAME)
    if existing and existing.get('resin_finish_version') == 2:
        return existing
    g = Graph(NAME)
    color = g.input('Base Color',(0.2,0.06,0.01,1),'Color')
    xyz = g.input('Coordinates mm',(0,0,0),'Vector')
    units = g.input('Scene Unit m',1,limits=(.000001,1000))
    rough = g.input('Roughness',.3,limits=(.03,1))
    polish = g.input('Polish',.3,limits=(0,1))
    noise = g.noise(xyz,5,'Fine Mold Skin',detail=2)
    patches = g.noise(xyz,.18,'Uneven Resin Gloss',detail=2)
    r = g.math('ADD',rough,g.math('MULTIPLY',g.math('SUBTRACT',patches,.5),.09))
    r = g.math('MINIMUM',g.math('MAXIMUM',r,.03),1)
    bump = g.node('ShaderNodeBump','Microscopic Mold Texture')
    bump.inputs['Strength'].default_value = .18
    g.set(bump.inputs['Height'],noise)
    g.set(bump.inputs['Distance'],g.math('DIVIDE',.000003,units))
    shader = g.node('ShaderNodeBsdfPrincipled','Molded Phenolic Resin')
    shader.inputs['Metallic'].default_value = 0
    shader.inputs['IOR'].default_value = 1.55
    shader.inputs['Coat IOR'].default_value = 1.46
    shader.inputs['Coat Roughness'].default_value = .22
    g.set(shader.inputs['Base Color'],color)
    g.set(shader.inputs['Roughness'],r)
    g.set(shader.inputs['Normal'],bump.outputs['Normal'])
    g.set(shader.inputs['Coat Weight'],polish)
    geometry = g.node('ShaderNodeNewGeometry','Smooth Resin Skin')
    g.set(shader.inputs['Coat Normal'],geometry.outputs['Normal'])
    deposits = g.node('ShaderNodeGroup','Shared Surface Deposits')
    deposits.node_tree = build_deposits_group()
    for name,value in [('Surface',shader.outputs[0]),('Coordinates mm',xyz),('Dust',g.input('Dust',0,limits=(0,1)))]:
        g.set(deposits.inputs[name],value)
    g.output('Shader',deposits.outputs['Shader'],'Shader')
    g.output('Dust Mask',deposits.outputs['Dust Mask'])
    g.output('Roughness',r)
    g.tree['resin_finish_version'] = 2
    g.layout()
    return g.tree
