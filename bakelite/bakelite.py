"""Two reference-inspired, entirely procedural Bakelite materials for Blender 5.2.
Selected meshes: assign Type 1. CLI --preview --render: rebuild the sample blend.
"""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY.parent))
try:
    from shared.resin_finish import build_group as resin_group
except ModuleNotFoundError:
    source = bpy.data.texts.get('shared_resin_finish.py')
    if source is None:
        raise RuntimeError('Keep shared/resin_finish.py beside the material folders.')
    scope = {'__name__':'shared_resin_finish'}
    exec(source.as_string(),scope)
    resin_group = scope['build_group']


class Graph:
    def __init__(self,name):
        self.tree = bpy.data.node_groups.new(name,'ShaderNodeTree')
        self.gin = self.node('NodeGroupInput','Controls')
        self.gout = self.node('NodeGroupOutput','Outputs')

    def node(self,kind,name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 205
        return n

    def set(self,socket,value):
        if isinstance(value,bpy.types.NodeSocket):
            self.tree.links.new(value,socket)
        else:
            socket.default_value = value

    def input(self,name,value,kind='Float',limits=None):
        s = self.tree.interface.new_socket(name=name,in_out='INPUT',socket_type='NodeSocket'+kind)
        s.default_value = value
        if limits:
            s.min_value,s.max_value = limits
        return self.gin.outputs[name]

    def output(self,name,value,kind='Float'):
        self.tree.interface.new_socket(name=name,in_out='OUTPUT',socket_type='NodeSocket'+kind)
        self.set(self.gout.inputs[name],value)

    def math(self,op,a,b=0,name=None):
        n = self.node('ShaderNodeMath',name or op)
        n.operation = op
        self.set(n.inputs[0],a)
        self.set(n.inputs[1],b)
        return n.outputs[0]

    def vector(self,op,a,b,name=None):
        n = self.node('ShaderNodeVectorMath',name or op)
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

    def noise(self,xyz,scale,name,detail=3,color=False):
        n = self.node('ShaderNodeTexNoise',name)
        self.set(n.inputs['Vector'],xyz)
        self.set(n.inputs['Scale'],scale)
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = .65
        return n.outputs['Color' if color else 'Fac']

    def ramp(self,value,low,high,name):
        n = self.node('ShaderNodeValToRGB',name)
        n.color_ramp.elements[0].position = low
        n.color_ramp.elements[1].position = high
        self.set(n.inputs[0],value)
        return n.outputs['Color']

    def layout(self):
        depth = {n:0 for n in self.tree.nodes}
        for _ in depth:
            changed = False
            for link in self.tree.links:
                d = depth[link.from_node]+1
                if d > depth[link.to_node]:
                    depth[link.to_node] = d
                    changed = True
            if not changed:
                break
        rows = {}
        for n,d in depth.items():
            row = rows.get(d,0)
            n.location = (d*290,-row*320)
            rows[d] = row+1


def warp(g,xyz,scale,strength,name,detail=3):
    noise = g.noise(xyz,scale,name,detail=detail,color=True)
    return g.vector('ADD',xyz,g.vector('SCALE',g.vector('SUBTRACT',noise,(.5,.5,.5)),strength),name+' Coordinates')


def fragment_pattern(g,xyz):
    # Each irregular domain carries a different orientation of short filler
    # bundles. Fine warp and breakup prevent a uniform cellular/wood texture.
    warped = warp(g,xyz,.11,2.7,'Fragment Edge Distortion')
    cells = g.node('ShaderNodeTexVoronoi','Random Filler Packets')
    cells.voronoi_dimensions,cells.feature = '3D','F1'
    g.set(cells.inputs['Vector'],warped)
    cells.inputs['Scale'].default_value = .105
    local = g.vector('SUBTRACT',warped,cells.outputs['Position'])
    rotate = g.node('ShaderNodeVectorRotate','Packet Fiber Orientation')
    rotate.rotation_type = 'EULER_XYZ'
    g.set(rotate.inputs['Vector'],local)
    g.set(rotate.inputs['Rotation'],g.vector('SCALE',cells.outputs['Color'],2*math.pi))
    fine = warp(g,rotate.outputs[0],.6,.45,'Ragged Short Strands')
    threads = g.noise(g.vector('MULTIPLY',fine,(.19,1.8,1.8)),1,'Short Amber Splinters',detail=3)
    threads = g.ramp(threads,.53,.69,'Splinter Edges')
    breakup = g.ramp(g.noise(warped,.23,'Irregular Resin Pools',detail=3),.35,.64,'Packet Coverage')
    mask = g.math('MULTIPLY',threads,breakup)
    fine_dust = g.ramp(g.noise(warped,3.5,'Fine Filler Specks',detail=2),.55,.75,'Small Amber Particles')
    return g.math('MAXIMUM',mask,g.math('MULTIPLY',fine_dust,.1),'Fragment Pattern')


def flowing_pattern(g,xyz):
    flow = warp(g,xyz,.008,50,'Broad Mold Flow',detail=1)
    flow = warp(g,flow,.022,3,'Secondary Flow Bends',detail=1)
    # Long correlated strands, with irregular spacing/length instead of wave rings.
    threads = g.noise(g.vector('MULTIPLY',flow,(.002,2.7,.12)),1,'Long Resin Flow Strands',detail=2)
    threads = g.ramp(threads,.52,.68,'Fine Flow Lines')
    fine = g.noise(g.vector('MULTIPLY',flow,(.015,5,.2)),1,'Broken Fine Fibers',detail=2)
    fine = g.ramp(fine,.58,.75,'Thin Amber Streaks')
    cloudy = g.noise(flow,.08,'Flow Visibility Patches',detail=2)
    return g.math('MULTIPLY',g.mix(.28,threads,fine,'Two Fiber Scales'),g.math('ADD',.45,cloudy),'Flow Pattern')


def build_core(pattern):
    g = Graph('Bakelite - '+pattern+' Core')
    g.tree['bakelite_pattern'] = pattern
    dark = g.input('Resin Color',(.10,.021,.006,1),'Color')
    light = g.input('Filler Color',(.48,.17,.035,1),'Color')
    scale = g.input('Pattern Scale',1,limits=(.1,10))
    contrast = g.input('Pattern Amount',1,limits=(0,1))
    rotation = g.input('Direction',(0,0,0),'Vector')
    seed = g.input('Seed',3,limits=(0,1000))
    rough = g.input('Roughness',.32,limits=(.03,1))
    polish = g.input('Polish',.25,limits=(0,1))
    units = g.input('Scene Unit m',bpy.context.scene.unit_settings.scale_length,limits=(.000001,1000))
    coord = g.node('ShaderNodeTexCoord','Object Coordinates')
    mm = g.vector('SCALE',coord.outputs['Object'],g.math('MULTIPLY',units,1000),'Coordinates mm')
    mapping = g.node('ShaderNodeMapping','Pattern Orientation')
    g.set(mapping.inputs['Vector'],g.vector('SCALE',mm,g.math('DIVIDE',1,scale)))
    g.set(mapping.inputs['Rotation'],rotation)
    xyz = g.vector('ADD',mapping.outputs['Vector'],g.vector('SCALE',(11.7,5.3,8.9),seed),'Seed Placement')
    mask = fragment_pattern(g,xyz) if pattern == 'Type 1 - Fragments' else flowing_pattern(g,xyz)
    visible = g.math('MULTIPLY',mask,contrast,'Embedded Filler')
    color = g.mix(visible,dark,light,'Filler Inside Resin')
    finish = g.node('ShaderNodeGroup','Shared Resin Surface')
    finish.node_tree = resin_group(Graph)
    for name,value in [('Base Color',color),('Coordinates mm',mm),('Scene Unit m',units),('Roughness',rough),('Polish',polish)]:
        g.set(finish.inputs[name],value)
    g.output('Shader',finish.outputs['Shader'],'Shader')
    g.output('Pattern Mask',mask)
    g.output('Visible Pattern',visible)
    g.output('Base Color',color,'Color')
    g.output('Surface Roughness',finish.outputs['Roughness'])
    g.layout()
    return g.tree


def public_group(core):
    g = Graph(core.name.replace(' Core',' Controls'))
    n = g.node('ShaderNodeGroup','Advanced Bakelite Settings')
    n.node_tree = core
    for socket in core.interface.items_tree:
        if socket.item_type != 'SOCKET' or socket.in_out != 'INPUT' or socket.name == 'Scene Unit m':
            continue
        kind = socket.socket_type.removeprefix('NodeSocket')
        limits = (socket.min_value,socket.max_value) if kind == 'Float' else None
        g.set(n.inputs[socket.name],g.input(socket.name,socket.default_value,kind,limits))
    for socket in g.tree.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.name == 'Direction':
            socket.subtype = 'EULER'
    g.output('Shader',n.outputs['Shader'],'Shader')
    g.layout()
    return g.tree


def make_material(name='Bakelite - Type 1 Amber',group=None,**settings):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes,mat.use_fake_user = True,True
    mat.node_tree.nodes.clear()
    n = mat.node_tree.nodes.new('ShaderNodeGroup')
    n.node_tree,n.name,n.width = group or public_group(build_core('Type 1 - Fragments')),'Bakelite Controls',310
    for key,value in settings.items():
        n.inputs[key].default_value = value
    out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (440,0)
    mat.node_tree.links.new(n.outputs['Shader'],out.inputs['Surface'])
    mat['bakelite_version'] = 1
    return mat


def preview(render):
    scene = bpy.data.scenes.new('Bakelite Reference Studies')
    bpy.context.window.scene = scene
    scene.unit_settings.system,scene.unit_settings.scale_length = 'METRIC',1
    fragments = public_group(build_core('Type 1 - Fragments'))
    flowing = public_group(build_core('Type 2 - Flow'))
    mats = [
        make_material('Bakelite - Type 1 Amber',fragments,**{'Resin Color':(.20,.035,.006,1),'Filler Color':(.65,.25,.045,1)}),
        make_material('Bakelite - Type 1 Dark',fragments,**{'Resin Color':(.055,.013,.004,1),'Filler Color':(.36,.12,.022,1),'Roughness':.36}),
        make_material('Bakelite - Type 2 Brown',flowing,**{'Resin Color':(.05,.008,.002,1),'Filler Color':(.25,.07,.013,1),'Roughness':.3}),
        make_material('Bakelite - Type 2 Golden',flowing,**{'Resin Color':(.095,.043,.009,1),'Filler Color':(.3,.16,.043,1),'Roughness':.36}),
    ]
    labels = ['TYPE 1 / AMBER','TYPE 1 / DARK','TYPE 2 / BROWN','TYPE 2 / GOLDEN']
    bodies = []
    label_mat = bpy.data.materials.new('Bakelite Labels')
    label_mat.diffuse_color = (.72,.72,.72,1)
    for i,mat in enumerate(mats):
        x,y = (i%2-.5)*.235,(.5-i//2)*.16
        bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,0))
        obj = bpy.context.object
        obj.name = labels[i]+' 200mm Panel'
        obj.dimensions = (.2,.105,.014)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bevel = obj.modifiers.new('Rounded Molded Edge','BEVEL')
        bevel.width,bevel.segments = .006,6
        obj.modifiers.new('Weighted Face Normals','WEIGHTED_NORMAL')
        obj.data.materials.append(mat)
        bodies.append(obj)
        # Curved sample tests continuity around the mold and the smooth resin skin.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=.025,location=(x+.062,y+.018,.024))
        sphere = bpy.context.object
        sphere.name = labels[i]+' Curved Sample'
        sphere.data.materials.append(mat)
        for face in sphere.data.polygons:
            face.use_smooth = True
        data = bpy.data.curves.new(labels[i],'FONT')
        data.body,data.align_x,data.size = labels[i],'CENTER',.005
        label = bpy.data.objects.new(labels[i],data)
        scene.collection.objects.link(label)
        label.location = (x,y-.068,0)
        data.materials.append(label_mat)
    scene.world = bpy.data.worlds.new('Bakelite Studio World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.18,.2,.24,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .3
    for name,pos,power,size in [('Key',(-.4,-.1,.4),10,.22),('Fill',(.3,-.15,.3),4,.18),('Rim',(-.1,.35,.25),1.5,.12)]:
        obj = bpy.data.objects.new(name,bpy.data.lights.new(name,'AREA'))
        scene.collection.objects.link(obj)
        obj.location = pos
        obj.rotation_euler = (-obj.location).to_track_quat('-Z','Y').to_euler()
        obj.data.energy,obj.data.shape,obj.data.size = power,'DISK',size
    cam = bpy.data.objects.new('Bakelite Camera',bpy.data.cameras.new('Bakelite Camera'))
    scene.collection.objects.link(cam)
    cam.location = (.19,-.38,.68)
    cam.rotation_euler = (-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type,cam.data.ortho_scale,cam.data.clip_start = 'ORTHO',.55,.001
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples,scene.cycles.use_denoising = 64,True
    scene.view_settings.exposure = -.5
    scene.render.resolution_x,scene.render.resolution_y = 1500,1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(DIRECTORY/'bakelite_preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    bodies[0].select_set(True)
    bpy.context.view_layer.objects.active = bodies[0]
    for name,path in [('bakelite.py',Path(__file__)),('shared_resin_finish.py',DIRECTORY.parent/'shared/resin_finish.py')]:
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        if path.exists():
            text.clear()
            text.write(path.read_text(encoding='utf-8'))
            text.filepath = str(path.resolve())
    bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY/'bakelite.blend'))
    if render:
        bpy.ops.render.render(write_still=True)
        for i in (1,2):
            target = bodies[i].location+Vector((-.025,0,.007))
            cam.location = target+Vector((0,-.025,.18))
            cam.rotation_euler = (target-cam.location).to_track_quat('-Z','Y').to_euler()
            cam.data.ortho_scale = .065
            scene.render.resolution_x = scene.render.resolution_y = 1000
            scene.render.filepath = str(DIRECTORY/('bakelite_type1_detail.png' if i == 1 else 'bakelite_type2_detail.png'))
            bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--render',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.preview:
        preview(args.render)
    else:
        selected = [o for o in bpy.context.selected_objects if o.type == 'MESH']
        if not selected:
            raise RuntimeError('Select mesh objects before running bakelite.py.')
        material = make_material()
        for obj in selected:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = material
            else:
                obj.data.materials.append(material)


if __name__ == '__main__':
    main()
