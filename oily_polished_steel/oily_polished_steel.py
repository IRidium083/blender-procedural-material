"""Blender 5.2: polished/chromed machinery steel with oil and grease.
Text Editor: run with selected meshes. CLI: --preview --render creates a studio
scene beside the script. One packed image, box projected; no UVs required.
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

NAME = "Oily Polished Machinery Steel"
IMAGE = "Machinery Oil Smear Mask"


def load_mask():
    image = bpy.data.images.get(IMAGE)
    if image is not None and image.packed_file:
        return image
    relative = Path("textures/oil_smear_mask.png")
    paths = [Path(__file__).resolve().parent / relative]
    if bpy.data.filepath:
        paths.append(Path(bpy.data.filepath).parent / relative)
    path = next((p for p in paths if p.is_file()), None)
    if path is None:
        raise FileNotFoundError("Keep textures/oil_smear_mask.png beside this script, or use the packed .blend.")
    image = bpy.data.images.load(str(path), check_existing=True)
    image.name = IMAGE
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


def make_material():
    image = load_mask()
    mat = bpy.data.materials.get(NAME) or bpy.data.materials.new(NAME)
    mat.use_nodes = True
    mat.diffuse_color = (0.55, 0.59, 0.62, 1)
    mat.node_tree.nodes.clear()
    g = bpy.data.node_groups.new(NAME, "ShaderNodeTree")
    for title, kind, value, limits in [
        ("Steel Color", "NodeSocketColor", (0.55, 0.59, 0.62, 1), None),
        ("Metal Roughness", "NodeSocketFloat", 0.16, (0.02, 1)),
        ("Oil Tint", "NodeSocketColor", (0.13, 0.075, 0.025, 1), None),
        ("Oil Amount", "NodeSocketFloat", 0.8, (0, 1)),
        ("Oil Scale", "NodeSocketFloat", 0.7, (0.01, 50)),
        ("Oil Roughness", "NodeSocketFloat", 0.24, (0.02, 1)),
        ("Grease Color", "NodeSocketColor", (0.025, 0.018, 0.009, 1), None),
        ("Crease Grease", "NodeSocketFloat", 0.7, (0, 1)),
        ("Grease Distance", "NodeSocketFloat", 0.16, (0.001, 5)),
        ("Machining Depth", "NodeSocketFloat", 0.0007, (0, 0.02)),
        ("Machining Scale", "NodeSocketFloat", 1.0, (0.01, 100)),
        ("Machining Rotation", "NodeSocketVector", (0, 0, 0), None),
    ]:
        s = g.interface.new_socket(name=title, in_out="INPUT", socket_type=kind)
        s.default_value = value
        if limits:
            s.min_value, s.max_value = limits
    g.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    def node(kind, title, x, y):
        n = g.nodes.new(kind)
        n.name = n.label = title
        n.location, n.width = (x, y), 190
        return n

    def link(a, out, b, inp):
        g.links.new(a.outputs[out], b.inputs[inp])

    def calc(title, op, x, y, a=0, b=0):
        n = node("ShaderNodeMath", title, x, y)
        n.operation = op
        n.inputs[0].default_value, n.inputs[1].default_value = a, b
        return n

    def mix(title, factor, first, second, x, y):
        n = node("ShaderNodeMixRGB", title, x, y)
        link(factor, 0, n, 0)
        for i, value in enumerate((first, second), 1):
            if len(value) == 2:
                link(value[0], value[1], n, i)
            else:
                n.inputs[i].default_value = value
        return n

    controls = node("NodeGroupInput", "Finish Controls", -1400, 700)
    coords = node("ShaderNodeTexCoord", "Object Coordinates", -1400, 250)
    scale = node("ShaderNodeVectorMath", "Oil Pattern Scale", -1150, 450)
    scale.operation = "SCALE"
    link(coords, "Object", scale, 0)
    link(controls, "Oil Scale", scale, "Scale")
    tex = node("ShaderNodeTexImage", "Oil Smears - Only Image Texture", -900, 600)
    tex.image, tex.projection, tex.projection_blend = image, "BOX", 0.3
    tex.extension, tex.interpolation = "REPEAT", "Linear"
    link(scale, "Vector", tex, "Vector")
    remap = node("ShaderNodeValToRGB", "Isolate Oil Residue", -650, 600)
    remap.color_ramp.elements[0].position = 0.065
    remap.color_ramp.elements[1].position = 0.48
    link(tex, "Color", remap, "Fac")
    oil = calc("Oil Coverage", "MULTIPLY", -400, 600)
    link(remap, "Color", oil, 0)
    link(controls, "Oil Amount", oil, 1)
    ao = node("ShaderNodeAmbientOcclusion", "Sheltered Grooves and Collars", -1150, -400)
    ao.samples = 16
    link(controls, "Grease Distance", ao, "Distance")
    cavity = calc("Cavity Mask", "SUBTRACT", -900, -400, a=1)
    link(ao, "AO", cavity, 1)
    gain = calc("Crease Concentration", "MULTIPLY", -650, -400, b=2.8)
    gain.use_clamp = True
    link(cavity, 0, gain, 0)
    breakup = calc("Grease Smear Breakup", "MULTIPLY_ADD", -650, -650, b=0.6)
    breakup.inputs[2].default_value = 0.4
    link(tex, "Color", breakup, 0)
    broken = calc("Irregular Crease Grease", "MULTIPLY", -400, -400)
    link(gain, 0, broken, 0)
    link(breakup, 0, broken, 1)
    grease = calc("Grease Coverage", "MULTIPLY", -150, -400)
    link(broken, 0, grease, 0)
    link(controls, "Crease Grease", grease, 1)
    mapping = node("ShaderNodeMapping", "Machining Direction", -1150, -950)
    link(coords, "Object", mapping, "Vector")
    link(controls, "Machining Rotation", mapping, "Rotation")
    machine_scale = node("ShaderNodeVectorMath", "Machining Frequency", -900, -950)
    machine_scale.operation = "SCALE"
    link(mapping, "Vector", machine_scale, 0)
    link(controls, "Machining Scale", machine_scale, "Scale")
    stretch = node("ShaderNodeVectorMath", "Circumferential Tool Lines", -650, -950)
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (2, 2, 320)
    link(machine_scale, "Vector", stretch, 0)
    machining = node("ShaderNodeTexNoise", "Fine Turning Marks", -400, -950)
    machining.inputs["Scale"].default_value = 1
    machining.inputs["Detail"].default_value = 2
    link(stretch, "Vector", machining, "Vector")
    bump = node("ShaderNodeBump", "Shallow Machining Relief", -150, -950)
    bump.inputs["Strength"].default_value = 0.18
    link(machining, "Fac", bump, "Height")
    link(controls, "Machining Depth", bump, "Distance")
    tint = mix("Oil Darkens Reflective Steel", oil, (controls, "Steel Color"),
               (controls, "Oil Tint"), -150, 650)
    roughness = mix("Smear Roughness", oil, (controls, "Metal Roughness"),
                    (controls, "Oil Roughness"), 100, 400)
    steel = node("ShaderNodeBsdfPrincipled", "Polished Steel with Oil Film", 400, 700)
    steel.inputs["Metallic"].default_value = 1
    steel.inputs["Coat Roughness"].default_value = 0.1
    steel.inputs["Coat IOR"].default_value = 1.46
    link(tint, 0, steel, "Base Color")
    link(roughness, 0, steel, "Roughness")
    link(oil, 0, steel, "Coat Weight")
    link(bump, "Normal", steel, "Normal")
    thick = node("ShaderNodeBsdfPrincipled", "Accumulated Nonmetallic Grease", 400, -150)
    thick.inputs["Metallic"].default_value = 0
    thick.inputs["Roughness"].default_value = 0.3
    thick.inputs["Coat Weight"].default_value = 0.35
    thick.inputs["Coat Roughness"].default_value = 0.12
    link(controls, "Grease Color", thick, "Base Color")
    combined = node("ShaderNodeMixShader", "Grease over Oiled Steel", 750, 600)
    link(grease, 0, combined, 0)
    link(steel, "BSDF", combined, 1)
    link(thick, "BSDF", combined, 2)
    out = node("NodeGroupOutput", "Surface", 1000, 600)
    link(combined, 0, out, "Shader")
    instance = mat.node_tree.nodes.new("ShaderNodeGroup")
    instance.node_tree, instance.width = g, 310
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    mat.node_tree.links.new(instance.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_preview(directory, render):
    scene = bpy.data.scenes.new("Oiled Machinery Studio")
    bpy.context.window.scene = scene
    mat = make_material()

    def turned(name, profile, location, closed=False):
        """Revolve a radius/Z profile around local Z; closed profiles form tubes."""
        count = 128
        vertices = [(r * math.cos(i * math.tau / count), r * math.sin(i * math.tau / count), z)
                    for r, z in profile for i in range(count)]
        faces = []
        for j in range(len(profile) if closed else len(profile) - 1):
            nxt = (j + 1) % len(profile)
            for i in range(count):
                ni = (i + 1) % count
                faces.append((j * count + i, j * count + ni, nxt * count + ni, nxt * count + i))
        if not closed:
            faces += [tuple(reversed(range(count))), tuple((len(profile)-1)*count+i for i in range(count))]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.data.materials.append(mat)
        for p in mesh.polygons:
            p.use_smooth = len(p.vertices) == 4 and abs(p.normal.z) < 0.9
        bevel = obj.modifiers.new("Machined Edge Radius", "BEVEL")
        bevel.width, bevel.segments = 0.012, 3
        return obj

    shaft = turned("Stepped Piston Shaft", [
        (0.6, -1.3), (0.6, -1.12), (0.47, -1.12), (0.47, -0.98),
        (0.59, -0.98), (0.59, -0.82), (0.34, -0.82), (0.34, 0.72),
        (0.55, 0.72), (0.55, 0.91), (0.48, 0.91), (0.48, 1.0),
        (0.55, 1.0), (0.55, 1.14), (0.48, 1.14), (0.48, 1.23),
        (0.55, 1.23), (0.55, 1.36)], (-0.75, 0, 0))
    turned("Hollow Cylinder Sleeve", [
        (0.68, -1.3), (0.68, -1.12), (0.58, -1.12), (0.58, 0.24),
        (0.68, 0.24), (0.68, 0.42), (0.43, 0.42), (0.43, -1.3)], (0.9, 0.2, 0), True)
    world = bpy.data.worlds.new("Machinery Studio World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.1, 0.12, 0.15, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, position, power, width, height in [
        ("Tall Key Strip", (-3, -4, 3), 950, 1.6, 5),
        ("Broad Fill", (4, -2, 2), 800, 3, 4),
        ("Rim Strip", (1, 3, 4), 1200, 2, 5),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.shape, data.size, data.size_y = power, "RECTANGLE", width, height
    camera = bpy.data.objects.new("Machinery Camera", bpy.data.cameras.new("Machinery Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (3.5, -6, 3.4)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 4.2
    configure_cycles(scene)
    scene.cycles.samples, scene.cycles.use_denoising = 96, True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "oily_polished_steel_preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    shaft.select_set(True)
    bpy.context.view_layer.objects.active = shaft
    bpy.data.texts.load(str(directory / "oily_polished_steel.py"))
    bpy.data.images[IMAGE].filepath = "//textures/oil_smear_mask.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "oily_polished_steel.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.preview:
        make_preview(Path(__file__).resolve().parent, args.render)
    else:
        targets = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not targets:
            raise RuntimeError("Select a mesh before running this script.")
        mat = make_material()
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
    print(f"Created {NAME}; Blender {bpy.app.version_string}")


if __name__ == "__main__":
    main()
