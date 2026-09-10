"""Blender 5.2: slightly used phosphated (Parkerized-style) steel.

Run in the Text Editor to assign to selected meshes. No UVs required.
One packed grayscale image supplies phosphate microrelief and roughness detail;
color, scratches and geometry-dependent wear remain procedural.
CLI: blender -b ../test.blend -P phosphated_gun_steel.py -- --preview --render
Preview creates a separate sample scene and saves beside this script.
"""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

NAME = "Phosphated Gun Steel - Slightly Used"
DETAIL_IMAGE = "Phosphate Microdetail"


def load_microdetail():
    """Use the packed image when rerunning from the delivered blend file."""
    image = bpy.data.images.get(DETAIL_IMAGE)
    if image is not None and image.packed_file:
        return image
    filename = Path("textures") / "phosphate_microdetail.png"
    candidates = [Path(__file__).resolve().parent / filename]
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).parent / filename)
    texture_path = next((p for p in candidates if p.is_file()), None)
    if texture_path is None:
        raise FileNotFoundError("Missing textures/phosphate_microdetail.png; keep the textures folder beside this script, or run from the supplied packed .blend.")
    image = bpy.data.images.load(str(texture_path), check_existing=True)
    image.name = DETAIL_IMAGE
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


def make_material():
    detail_image = load_microdetail()
    mat = bpy.data.materials.get(NAME) or bpy.data.materials.new(NAME)
    mat.use_nodes = True
    mat.diffuse_color = (0.035, 0.041, 0.038, 1)
    mat.node_tree.nodes.clear()
    group = bpy.data.node_groups.new(NAME, "ShaderNodeTree")
    controls = [
        ("Meters Per Unit", "NodeSocketFloat", bpy.context.scene.unit_settings.scale_length, (0.000001, 1000)),
        ("Finish Color", "NodeSocketColor", (0.035, 0.041, 0.038, 1), None),
        ("Exposed Steel", "NodeSocketColor", (0.24, 0.27, 0.28, 1), None),
        ("Roughness", "NodeSocketFloat", 0.57, (0, 1)),
        ("Edge Wear", "NodeSocketFloat", 0.38, (0, 1)),
        ("Edge Width", "NodeSocketFloat", 0.0005, (0.00001, 0.05)),
        ("Scratches", "NodeSocketFloat", 0.22, (0, 1)),
        ("Scratch Depth", "NodeSocketFloat", 0.00003, (0, 0.001)),
        ("Grain Depth", "NodeSocketFloat", 0.00001, (0, 0.001)),
        ("Pattern Scale", "NodeSocketFloat", 10.0, (0.01, 1000)),
        ("Microdetail Tiling", "NodeSocketFloat", 2.0, (0.01, 50)),
        ("Micro Roughness", "NodeSocketFloat", 0.12, (0, 0.5)),
    ]
    for name, kind, value, limits in controls:
        s = group.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
        s.default_value = value
        if limits:
            s.min_value, s.max_value = limits
    group.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    def node(kind, name, x, y):
        n = group.nodes.new(kind)
        n.name = n.label = name
        n.location = (x, y)
        n.width = 190
        return n

    def link(a, output, b, input_):
        group.links.new(a.outputs[output], b.inputs[input_])

    def math(name, op, x, y, a=None, b=None):
        n = node("ShaderNodeMath", name, x, y)
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is not None:
                n.inputs[i].default_value = v
        return n

    def noise(name, source, frequency, x, y, detail=2):
        n = node("ShaderNodeTexNoise", name, x, y)
        n.noise_dimensions = "3D"
        n.inputs["Scale"].default_value = frequency
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = 0.65
        link(source, "Vector", n, "Vector")
        return n

    def mix(name, factor, first, second, x, y):
        n = node("ShaderNodeMixRGB", name, x, y)
        link(factor, 0, n, 0)
        for i, val in enumerate((first, second), 1):
            if len(val) == 2:
                link(val[0], val[1], n, i)
            else:
                n.inputs[i].default_value = val
        return n

    inp = node("NodeGroupInput", "Finish Controls", -1250, 650)
    tex = node("ShaderNodeTexCoord", "Object Coordinates", -1250, 250)
    scale = node("ShaderNodeVectorMath", "Pattern Scale", -1000, 250)
    scale.operation = "SCALE"
    metric = node("ShaderNodeVectorMath", "Coordinates in Meters", -1550, 200)
    metric.operation = "SCALE"
    link(tex, "Object", metric, 0)
    link(inp, "Meters Per Unit", metric, "Scale")
    link(metric, "Vector", scale, 0)

    def distance(control, target):
        convert = node("ShaderNodeMath", control + " to Scene Units", -1550, -100 - 180 * len([n for n in group.nodes if n.name.endswith("to Scene Units")]))
        convert.operation = "DIVIDE"
        link(inp, control, convert, 0)
        link(inp, "Meters Per Unit", convert, 1)
        link(convert, 0, target, "Distance")

    link(inp, "Pattern Scale", scale, "Scale")
    mottle = noise("Subtle Phosphate Variation", scale, 5, -750, 450, 3)
    detail_scale = node("ShaderNodeVectorMath", "Microdetail Tiling", -1250, -1150)
    detail_scale.operation = "SCALE"
    link(scale, "Vector", detail_scale, 0)
    link(inp, "Microdetail Tiling", detail_scale, "Scale")
    grain = node("ShaderNodeTexImage", "Phosphate Microdetail - Only Image Texture", -1000, -1150)
    grain.image = detail_image
    grain.projection = "BOX"
    grain.projection_blend = 0.25
    grain.extension = "REPEAT"
    grain.interpolation = "Linear"
    link(detail_scale, "Vector", grain, "Vector")
    stretch = node("ShaderNodeVectorMath", "Long Sparse Abrasion", -1000, -250)
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1.5, 45, 45)
    link(scale, "Vector", stretch, 0)
    scratches = noise("Hairline Scratch Noise", stretch, 1, -750, -250)
    lines = node("ShaderNodeValToRGB", "Sparse Scratch Threshold", -500, -250)
    lines.color_ramp.elements[0].position = 0.69
    lines.color_ramp.elements[1].position = 0.735
    link(scratches, "Fac", lines, "Fac")
    scratch = math("Scratch Strength", "MULTIPLY", -250, -250)
    link(lines, "Color", scratch, 0)
    link(inp, "Scratches", scratch, 1)
    ao = node("ShaderNodeAmbientOcclusion", "Convex Edge Detection", -1000, -600)
    ao.inside = True
    ao.samples = 16
    distance("Edge Width", ao)
    inverse = math("Convex Wear Mask", "SUBTRACT", -750, -600, 1)
    link(ao, "AO", inverse, 1)
    gain = math("Narrow Edge Polish", "MULTIPLY", -500, -600, b=4)
    gain.use_clamp = True
    link(inverse, 0, gain, 0)
    irregular = math("Broken Edge Polish", "MULTIPLY", -250, -600)
    link(gain, 0, irregular, 0)
    link(mottle, "Fac", irregular, 1)
    edge = math("Edge Wear Strength", "MULTIPLY", 0, -600)
    link(irregular, 0, edge, 0)
    link(inp, "Edge Wear", edge, 1)
    wear = math("Light Handling Wear", "MAXIMUM", 250, -300)
    link(edge, 0, wear, 0)
    link(scratch, 0, wear, 1)
    dark = node("ShaderNodeMixRGB", "Subtle Finish Mottling", -250, 450)
    dark.blend_type = "MULTIPLY"
    dark.inputs[0].default_value = 0.18
    link(inp, "Finish Color", dark, 1)
    link(mottle, "Fac", dark, 2)
    color = mix("Worn Phosphate Reveals Steel", wear, (dark, 0), (inp, "Exposed Steel"), 500, 450)
    centered = math("Centered Microdetail", "SUBTRACT", -750, -1150, b=0.5)
    link(grain, "Color", centered, 0)
    rough_var = math("Grain Roughness Variation", "MULTIPLY", -250, 100)
    link(centered, 0, rough_var, 0)
    link(inp, "Micro Roughness", rough_var, 1)
    rough_base = math("Matte Phosphate Roughness", "ADD", 0, 100)
    rough_base.use_clamp = True
    link(rough_var, 0, rough_base, 0)
    link(inp, "Roughness", rough_base, 1)
    roughness = mix("Polished Wear Roughness", wear, (rough_base, 0), (0.28, 0.28, 0.28, 1), 500, 150)
    bump = node("ShaderNodeBump", "Microscopic Phosphate Texture", 0, -900)
    bump.inputs["Strength"].default_value = 0.18
    link(grain, "Color", bump, "Height")
    distance("Grain Depth", bump)
    cut = node("ShaderNodeBump", "Shallow Hairline Scratches", 250, -900)
    cut.invert = True
    cut.inputs["Strength"].default_value = 0.2
    distance("Scratch Depth", cut)
    link(scratch, 0, cut, "Height")
    link(bump, "Normal", cut, "Normal")
    shader = node("ShaderNodeBsdfPrincipled", "Dark Matte Gun Steel", 800, 450)
    shader.inputs["Metallic"].default_value = 0.85
    link(color, 0, shader, "Base Color")
    link(roughness, 0, shader, "Roughness")
    link(cut, "Normal", shader, "Normal")
    out = node("NodeGroupOutput", "Surface", 1100, 450)
    link(shader, "BSDF", out, "Shader")
    instance = mat.node_tree.nodes.new("ShaderNodeGroup")
    instance.node_tree = group
    instance.width = 290
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (380, 0)
    mat.node_tree.links.new(instance.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_preview(mat, directory, render):
    scene = bpy.data.scenes.new("Phosphated Steel Studio")
    bpy.context.window.scene = scene

    def block(name, location, dimensions, bevel=0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        if bevel:
            mod = obj.modifiers.new("Machined Edge Radius", "BEVEL")
            mod.width, mod.segments = bevel, 3
        return obj

    body = block("Machined Steel Sample", (0, 0, 0), (2.8, 1.6, 1.25))
    cutter = block("Pocket Cutter", (0, -0.75, 0.08), (1.85, 0.6, 0.62))
    bpy.context.view_layer.objects.active = body
    boolean = body.modifiers.new("Recessed Pocket", "BOOLEAN")
    boolean.operation, boolean.object = "DIFFERENCE", cutter
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bevel = body.modifiers.new("Small Machined Chamfer", "BEVEL")
    bevel.width, bevel.segments = 0.025, 3
    block("Sharp Raised Rib", (0, 0.1, 0.73), (2.25, 0.35, 0.21), 0.006)
    for x in (-0.94, 0.94):
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.14, depth=0.06, location=(x, -0.44, 0.65))
        obj = bpy.context.object
        obj.name = "Circular Machining Sample"
        obj.data.materials.append(mat)
        mod = obj.modifiers.new("Rim Bevel", "BEVEL")
        mod.width, mod.segments = 0.008, 3

    world = bpy.data.worlds.new("Phosphate Studio World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.14, 0.17, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, position, power, size in [
        ("Large Key", (1, -4, 5), 1000, 4),
        ("Soft Fill", (-4, -2, 2), 700, 3),
        ("Edge Strip", (2, 3, 4), 1300, 3),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.shape, data.size = power, "DISK", size
    camera = bpy.data.objects.new("Phosphate Preview Camera", bpy.data.cameras.new("Phosphate Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (3.8, -5.8, 3.4)
    camera.rotation_euler = (Vector((0, 0, 0.1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 4.2
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 850
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "phosphated_gun_steel_preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    # Embed the script for convenient editing from the delivered .blend.
    bpy.data.texts.load(str(directory / "phosphated_gun_steel.py"))
    mat.node_tree.nodes.get("Group").node_tree.nodes["Phosphate Microdetail - Only Image Texture"].image.filepath = "//textures/phosphate_microdetail.png"
    sys.path.insert(0, str(directory.parent))
    from real_scale_utils import resize_studio
    resize_studio(scene, body, 0.2 if "Grip" in body.name else 0.28)
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "phosphated_gun_steel.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    targets = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not args.preview and not targets:
        raise RuntimeError("Select at least one mesh to assign the material.")
    mat = make_material()
    if args.preview:
        make_preview(mat, Path(__file__).resolve().parent, args.render)
    else:
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
    print(f"Created {NAME}; Blender {bpy.app.version_string}")


if __name__ == "__main__":
    main()
