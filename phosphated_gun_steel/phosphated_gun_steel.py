"""Blender 5.2: slightly used phosphated (Parkerized-style) steel.

Run in the Text Editor to assign to selected meshes. No UVs required.
One packed grayscale image supplies phosphate microrelief and roughness detail;
color, scratches and geometry-dependent wear remain procedural.
CLI: blender -b ../test.blend -P phosphated_gun_steel.py -- --preview --render
Preview creates a separate sample scene and saves beside this script.
"""
import argparse
import math as mathlib
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

NAME = "Phosphated Gun Steel - Slightly Used"
EEVEE_NAME = NAME + " - Eevee"
EDGE_ATTRIBUTE = "gun_steel_convex_sharp_edge"
EDGE_GROUP = "Gun Steel - Convex Sharp Edge Tags"
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


def build_edge_tags():
    """Tag outward edges above 45 degrees on evaluated mesh geometry."""
    existing = bpy.data.node_groups.get(EDGE_GROUP)
    if existing and existing.get("gun_edge_tags_version") == 1:
        return existing
    tree = bpy.data.node_groups.new(EDGE_GROUP, "GeometryNodeTree")
    tree["gun_edge_tags_version"] = 1
    tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    source = tree.nodes.new("NodeGroupInput")
    result = tree.nodes.new("NodeGroupOutput")
    angle = tree.nodes.new("GeometryNodeInputMeshEdgeAngle")
    convex = tree.nodes.new("ShaderNodeMath")
    # Verified in Blender 5.2 on outward/inside-out cubes: the evaluated edge
    # angle here is positive for convex and negative for concave joins.
    convex.operation = "GREATER_THAN"
    convex.inputs[1].default_value = mathlib.radians(45)
    tree.links.new(angle.outputs["Signed Angle"], convex.inputs[0])
    store = tree.nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT", "POINT"
    store.inputs["Name"].default_value = EDGE_ATTRIBUTE
    tree.links.new(source.outputs["Geometry"], store.inputs["Geometry"])
    tree.links.new(convex.outputs[0], store.inputs["Value"])
    tree.links.new(store.outputs["Geometry"], result.inputs["Geometry"])
    for n, xy in ((source, (-650, 100)), (angle, (-650, -150)), (convex, (-400, -150)),
                  (store, (-150, 100)), (result, (100, 100))):
        n.location = xy
    return tree


def add_edge_tags(obj):
    if obj.type != "MESH":
        return
    modifier = next((m for m in obj.modifiers if m.type == "NODES" and
                     m.node_group and m.node_group.name == EDGE_GROUP), None)
    if modifier is None:
        modifier = obj.modifiers.new("Convex Edge Tags for Eevee", "NODES")
    modifier.node_group = build_edge_tags()
    # Keep this after bevel/subdivision modifiers so a rounded final edge is not
    # classified from an earlier, sharp version of the mesh.
    obj.modifiers.move(obj.modifiers.find(modifier.name), len(obj.modifiers)-1)


def make_material(engine="CYCLES"):
    assert engine in {"CYCLES", "EEVEE"}
    detail_image = load_microdetail()
    material_name = NAME if engine == "CYCLES" else EEVEE_NAME
    mat = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
    mat.use_nodes = mat.use_fake_user = True
    mat.diffuse_color = (0.035, 0.041, 0.038, 1)
    mat.node_tree.nodes.clear()
    group = bpy.data.node_groups.new(material_name, "ShaderNodeTree")
    controls = [
        ("Meters Per Unit", "NodeSocketFloat", bpy.context.scene.unit_settings.scale_length, (0.000001, 1000)),
        ("Finish Color", "NodeSocketColor", (0.035, 0.041, 0.038, 1), None),
        ("Exposed Steel", "NodeSocketColor", (0.24, 0.27, 0.28, 1), None),
        ("Roughness", "NodeSocketFloat", 0.57, (0, 1)),
        ("Edge Wear", "NodeSocketFloat", 0.65, (0, 1)),
        ("Edge Width", "NodeSocketFloat", 0.0012, (0.00001, 0.05)),
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

    def distance(control, target, socket="Distance"):
        convert = node("ShaderNodeMath", control + " to Scene Units", -1550, -100 - 180 * len([n for n in group.nodes if n.name.endswith("to Scene Units")]))
        convert.operation = "DIVIDE"
        link(inp, control, convert, 0)
        link(inp, "Meters Per Unit", convert, 1)
        link(convert, 0, target, socket)
        return convert

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
    # AO supplies width; the renderer-specific signal classifies convexity.
    sharp = node("ShaderNodeMapRange", "Sharp Edges Only", -250, -820)
    sharp.interpolation_type = "SMOOTHSTEP"
    sharp.clamp = True
    if engine == "CYCLES":
        geometry = node("ShaderNodeNewGeometry", "Mesh Curvature (Cycles)", -1000, -820)
        sharp.inputs["From Min"].default_value = 0.56
        sharp.inputs["From Max"].default_value = 0.67
        link(geometry, "Pointiness", sharp, "Value")
    else:
        attribute = node("ShaderNodeAttribute", "Convex Edge Attribute (Eevee)", -1000, -820)
        attribute.attribute_name = EDGE_ATTRIBUTE
        sharp.inputs["From Min"].default_value = 0.04
        sharp.inputs["From Max"].default_value = 0.20
        link(attribute, "Fac", sharp, "Value")
    inverse = math("Convex Wear Mask", "SUBTRACT", -750, -600, 1)
    link(ao, "AO", inverse, 1)
    gain = math("Narrow Edge Polish", "MULTIPLY", -500, -600, b=4)
    gain.use_clamp = True
    link(inverse, 0, gain, 0)
    edge_location = node("ShaderNodeVectorMath", "Wear Variation in Meters", -1250, -1400)
    edge_location.operation = "SCALE"
    link(metric, "Vector", edge_location, 0)
    edge_location.inputs["Scale"].default_value = 45
    coarse = noise("Interrupted Edge Wear", edge_location, 1, -1000, -1400, 2)
    coarse_mask = node("ShaderNodeMapRange", "Worn and Intact Sections", -750, -1400)
    coarse_mask.interpolation_type = "SMOOTHSTEP"
    coarse_mask.inputs["From Min"].default_value = 0.39
    coarse_mask.inputs["From Max"].default_value = 0.66
    link(coarse, "Fac", coarse_mask, "Value")
    fine_location = node("ShaderNodeVectorMath", "Small Edge Breakup in Meters", -1250, -1650)
    fine_location.operation = "SCALE"
    link(metric, "Vector", fine_location, 0)
    fine_location.inputs["Scale"].default_value = 350
    fine = noise("Fine Chipped Edge Wear", fine_location, 1, -1000, -1650, 2)
    fine_mask = node("ShaderNodeMapRange", "Irregular Wear Boundary", -750, -1650)
    fine_mask.interpolation_type = "SMOOTHSTEP"
    fine_mask.inputs["From Min"].default_value = 0.27
    fine_mask.inputs["From Max"].default_value = 0.7
    link(fine, "Fac", fine_mask, "Value")
    broken = math("Varied Edge Polish", "MULTIPLY", -500, -1400)
    link(coarse_mask, "Result", broken, 0)
    link(fine_mask, "Result", broken, 1)
    irregular = math("Wear Only on Sharp Edges", "MULTIPLY", -250, -600)
    link(gain, 0, irregular, 0)
    link(sharp, "Result", irregular, 1)
    fragments = math("Interrupted Sharp Edge Wear", "MULTIPLY", 0, -750)
    link(irregular, 0, fragments, 0)
    link(broken, 0, fragments, 1)
    edge = math("Edge Wear Strength", "MULTIPLY", 0, -600)
    link(fragments, 0, edge, 0)
    link(inp, "Edge Wear", edge, 1)
    group.interface.new_socket(name="Sharp Edge Mask", in_out="OUTPUT", socket_type="NodeSocketFloat")
    group.interface.new_socket(name="Edge Wear Mask", in_out="OUTPUT", socket_type="NodeSocketFloat")
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
    link(sharp, "Result", out, "Sharp Edge Mask")
    link(edge, 0, out, "Edge Wear Mask")
    instance = mat.node_tree.nodes.new("ShaderNodeGroup")
    instance.node_tree = group
    instance.width = 290
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (380, 0)
    mat.node_tree.links.new(instance.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_preview(mat, eevee_mat, directory, render):
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
    block("Sharp Raised Rib", (0, 0.1, 0.73), (2.25, 0.35, 0.21))
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
    configure_cycles(scene)
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
    samples = [obj for obj in scene.objects if obj.type == "MESH"]
    for obj in samples:
        add_edge_tags(obj)
    if render:
        bpy.ops.render.render(write_still=True)
        for obj in samples:
            obj.data.materials[0] = eevee_mat
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.filepath = str(directory / "phosphated_gun_steel_eevee.png")
        bpy.ops.render.render(write_still=True)
        for obj in samples:
            obj.data.materials[0] = mat
        configure_cycles(scene)
        scene.render.filepath = str(directory / "phosphated_gun_steel_preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "phosphated_gun_steel.blend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--eevee", action="store_true", help="Assign the Eevee material and convex-edge Geometry Nodes tag.")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    targets = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not args.preview and not targets:
        raise RuntimeError("Select at least one mesh to assign the material.")
    eevee = args.eevee or (not args.preview and bpy.context.scene.render.engine == "BLENDER_EEVEE")
    mat = make_material("EEVEE" if eevee and not args.preview else "CYCLES")
    if args.preview:
        eevee_mat = make_material("EEVEE")
        make_preview(mat, eevee_mat, Path(__file__).resolve().parent, args.render)
    else:
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
            if eevee:
                add_edge_tags(obj)
    print(f"Created {mat.name}; Blender {bpy.app.version_string}")


if __name__ == "__main__":
    main()
