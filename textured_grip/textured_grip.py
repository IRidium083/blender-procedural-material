"""Blender 5.2 hybrid molded plastic / hard rubber grip.

Text Editor: run to assign to selected meshes.
CLI: blender -b ../test.blend -P textured_grip.py -- --preview --render
Use --plastic for the harder, slightly shinier polymer preset.
One packed grayscale image supplies stipple height and roughness detail.
Color, micro grain and handling wear remain procedural; no UVs required.
"""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

DETAIL_IMAGE = "Molded Grip Height"


def load_grip_height():
    """Reuse the packed shared image when running from the delivered .blend."""
    image = bpy.data.images.get(DETAIL_IMAGE)
    if image is not None and image.packed_file:
        return image
    relative = Path("textures") / "molded_grip_height.png"
    candidates = [Path(__file__).resolve().parent / relative]
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).parent / relative)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError("Missing textures/molded_grip_height.png. Keep textures beside this script or use the packed preview .blend.")
    image = bpy.data.images.load(str(path), check_existing=True)
    image.name = DETAIL_IMAGE
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


def make_material(plastic=False):
    detail_image = load_grip_height()
    name = "Textured Grip - " + ("Hard Polymer" if plastic else "Hard Rubber")
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (0.022, 0.027, 0.03, 1)
    mat.node_tree.nodes.clear()
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for title, kind, value, limits in [
        ("Meters Per Unit", "NodeSocketFloat", bpy.context.scene.unit_settings.scale_length, (0.000001, 1000)),
        ("Base Color", "NodeSocketColor", (0.022, 0.027, 0.03, 1), None),
        ("Texture Scale", "NodeSocketFloat", 567.0, (1, 10000)),
        ("Texture Depth", "NodeSocketFloat", 0.0003 if plastic else 0.0005, (0, 0.005)),
        ("Micro Grain", "NodeSocketFloat", 0.00003, (0, 0.001)),
        ("Roughness", "NodeSocketFloat", 0.46 if plastic else 0.68, (0, 1)),
        ("Handling Wear", "NodeSocketFloat", 0.16, (0, 1)),
        ("Edge Width", "NodeSocketFloat", 0.001, (0.00001, 0.05)),
        ("Texture Roughness", "NodeSocketFloat", 0.12, (0, 0.5)),
        ("Mould Line", "NodeSocketBool", False, None),
        ("Mould Width", "NodeSocketFloat", 0.0008, (0.00001, 0.01)),
        ("Mould Height", "NodeSocketFloat", 0.0002, (0, 0.003)),
        ("Mould Offset", "NodeSocketFloat", 0.0, (-1, 1)),
        ("Mould Plane Normal", "NodeSocketVector", (1, 0, 0), None),
    ]:
        s = group.interface.new_socket(name=title, in_out="INPUT", socket_type=kind)
        s.default_value = value
        if limits:
            s.min_value, s.max_value = limits
    group.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    def node(kind, title, x, y):
        n = group.nodes.new(kind)
        n.name = n.label = title
        n.location, n.width = (x, y), 190
        return n

    def link(a, out, b, inp):
        group.links.new(a.outputs[out], b.inputs[inp])

    def math(title, operation, x, y, b=0):
        n = node("ShaderNodeMath", title, x, y)
        n.operation = operation
        n.inputs[1].default_value = b
        return n

    inp = node("NodeGroupInput", "Grip Controls", -1300, 600)
    coords = node("ShaderNodeTexCoord", "Object Space - No UVs", -1300, 200)
    scale = node("ShaderNodeVectorMath", "Stipple Frequency", -1050, 200)
    scale.operation = "SCALE"
    metric = node("ShaderNodeVectorMath", "Coordinates in Meters", -1550, 200)
    metric.operation = "SCALE"
    link(coords, "Object", metric, 0)
    link(inp, "Meters Per Unit", metric, "Scale")
    link(metric, "Vector", scale, 0)

    def distance(control, target):
        convert = node("ShaderNodeMath", control + " to Scene Units", -1550, -100 - 180 * len([n for n in group.nodes if n.name.endswith("to Scene Units")]))
        convert.operation = "DIVIDE"
        link(inp, control, convert, 0)
        link(inp, "Meters Per Unit", convert, 1)
        link(convert, 0, target, "Distance")

    link(inp, "Texture Scale", scale, "Scale")
    # Preserve approximately the original scale control's grain density.
    image_scale = node("ShaderNodeVectorMath", "Stipple Image Repeat Scale", -1050, 950)
    image_scale.operation = "SCALE"
    image_scale.inputs["Scale"].default_value = 1 / 35
    link(scale, "Vector", image_scale, 0)
    profile = node("ShaderNodeTexImage", "Molded Stipple - Only Image Texture", -800, 650)
    profile.image = detail_image
    profile.projection = "BOX"
    profile.projection_blend = 0.25
    profile.extension = "REPEAT"
    profile.interpolation = "Linear"
    link(image_scale, "Vector", profile, "Vector")
    grain = node("ShaderNodeTexNoise", "Fine Mold Grain", -800, -50)
    grain.inputs["Scale"].default_value = 5
    grain.inputs["Detail"].default_value = 2
    link(scale, "Vector", grain, "Vector")
    variation = node("ShaderNodeMixRGB", "Subtle Procedural Color", -250, 550)
    variation.blend_type = "MULTIPLY"
    variation.inputs[0].default_value = 0.14
    link(inp, "Base Color", variation, 1)
    link(grain, "Fac", variation, 2)
    ao = node("ShaderNodeAmbientOcclusion", "Raised Edge Handling", -1050, -450)
    ao.inside, ao.samples = True, 16
    distance("Edge Width", ao)
    inverse = math("Convex Edge Mask", "SUBTRACT", -800, -450)
    inverse.inputs[0].default_value = 1
    link(ao, "AO", inverse, 1)
    gain = math("Edge Polish Band", "MULTIPLY", -550, -450, 3)
    gain.use_clamp = True
    link(inverse, 0, gain, 0)
    wear = math("Light Handling Polish", "MULTIPLY", -300, -450)
    link(gain, 0, wear, 0)
    link(inp, "Handling Wear", wear, 1)
    smoothing = math("Remaining Mold Relief", "SUBTRACT", -50, -450)
    smoothing.inputs[0].default_value = 1
    link(wear, 0, smoothing, 1)
    depth = math("Worn Texture Depth", "MULTIPLY", 200, -450)
    link(smoothing, 0, depth, 0)
    link(inp, "Texture Depth", depth, 1)
    centered = math("Centered Stipple Detail", "SUBTRACT", -550, 150, 0.5)
    link(profile, "Color", centered, 0)
    rough_variation = math("Stipple Roughness Variation", "MULTIPLY", -550, -100)
    link(centered, 0, rough_variation, 0)
    link(inp, "Texture Roughness", rough_variation, 1)
    rough = math("Base Roughness", "ADD", -300, -100)
    link(rough_variation, 0, rough, 0)
    link(inp, "Roughness", rough, 1)
    polish = math("Polish Roughness Reduction", "MULTIPLY", -50, -100, 0.3)
    link(wear, 0, polish, 0)
    final_rough = math("Handled Surface Roughness", "SUBTRACT", 200, 100)
    final_rough.use_clamp = True
    link(rough, 0, final_rough, 0)
    link(polish, 0, final_rough, 1)
    micro = node("ShaderNodeBump", "Microscopic Mold Texture", -300, -800)
    micro.inputs["Strength"].default_value = 0.22
    link(grain, "Fac", micro, "Height")
    distance("Micro Grain", micro)
    bump = node("ShaderNodeBump", "Raised Grip Stipple", 450, -450)
    bump.inputs["Strength"].default_value = 0.65
    link(profile, "Color", bump, "Height")
    depth_units = math("Stipple Depth to Scene Units", "DIVIDE", 450, -700)
    link(depth, 0, depth_units, 0)
    link(inp, "Meters Per Unit", depth_units, 1)
    link(depth_units, 0, bump, "Distance")
    link(micro, "Normal", bump, "Normal")
    # Distance to a parting plane through the local origin, in meters. This
    # follows the front, back and rounded ends without UVs or another image.
    plane_normal = node("ShaderNodeVectorMath", "Parting Plane Normal", -1300, -1400)
    plane_normal.operation = "NORMALIZE"
    link(inp, "Mould Plane Normal", plane_normal, 0)
    plane = node("ShaderNodeVectorMath", "Distance Along Parting Normal", -1050, -1400)
    plane.operation = "DOT_PRODUCT"
    link(metric, "Vector", plane, 0)
    link(plane_normal, "Vector", plane, 1)
    offset = math("Parting Plane Offset", "SUBTRACT", -800, -1400)
    link(plane, "Value", offset, 0)
    link(inp, "Mould Offset", offset, 1)
    absolute = math("Distance to Parting Plane", "ABSOLUTE", -550, -1400)
    link(offset, 0, absolute, 0)
    half_width = math("Mould Half Width", "MULTIPLY", -800, -1700, 0.5)
    link(inp, "Mould Width", half_width, 0)
    safe_width = math("Safe Mould Width", "MAXIMUM", -550, -1700, 0.000005)
    link(half_width, 0, safe_width, 0)
    normalized = math("Normalized Seam Distance", "DIVIDE", -300, -1400)
    link(absolute, 0, normalized, 0)
    link(safe_width, 0, normalized, 1)
    ridge = math("Mould Ridge Profile", "SUBTRACT", -50, -1400)
    ridge.inputs[0].default_value = 1
    ridge.use_clamp = True
    link(normalized, 0, ridge, 1)
    rounded = math("Rounded Mould Ridge", "POWER", 200, -1400, 2)
    link(ridge, 0, rounded, 0)
    enabled = math("Optional Mould Mask", "MULTIPLY", 450, -1400)
    link(rounded, 0, enabled, 0)
    link(inp, "Mould Line", enabled, 1)
    # Reduce the coarse stipple at the ridge so the parting line reads cleanly.
    flatten = math("Smooth Mould Ridge", "MULTIPLY", 200, -1700, 0.85)
    link(enabled, 0, flatten, 0)
    remaining = math("Remaining Stipple at Seam", "SUBTRACT", 450, -1700)
    remaining.inputs[0].default_value = 1
    link(flatten, 0, remaining, 1)
    seam_depth = math("Stipple with Mould Line", "MULTIPLY", 700, -1700)
    link(depth_units, 0, seam_depth, 0)
    link(remaining, 0, seam_depth, 1)
    link(seam_depth, 0, bump, "Distance")
    seam_bump = node("ShaderNodeBump", "Raised Mould Parting Line", 750, -950)
    seam_bump.inputs["Strength"].default_value = 0.65
    link(enabled, 0, seam_bump, "Height")
    distance("Mould Height", seam_bump)
    link(bump, "Normal", seam_bump, "Normal")
    shader = node("ShaderNodeBsdfPrincipled", "Nonmetallic Molded Grip", 750, 450)
    shader.inputs["Metallic"].default_value = 0
    shader.inputs["IOR"].default_value = 1.48
    link(variation, 0, shader, "Base Color")
    link(final_rough, 0, shader, "Roughness")
    link(seam_bump, "Normal", shader, "Normal")
    out = node("NodeGroupOutput", "Surface", 1050, 450)
    link(shader, "BSDF", out, "Shader")
    instance = mat.node_tree.nodes.new("ShaderNodeGroup")
    instance.node_tree, instance.width = group, 290
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (380, 0)
    mat.node_tree.links.new(instance.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_preview(directory, render):
    scene = bpy.data.scenes.new("Textured Grip Studio")
    bpy.context.window.scene = scene
    rubber, plastic = make_material(), make_material(True)
    for material in (rubber, plastic):
        instance = next(n for n in material.node_tree.nodes if n.type == "GROUP")
        instance.inputs["Mould Line"].default_value = True

    def block(name, location, dimensions, mat, bevel):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name, obj.dimensions = name, dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        mod = obj.modifiers.new("Molded Corner Radius", "BEVEL")
        mod.width, mod.segments = bevel, 8
        return obj

    body = block("Hard Rubber Grip Sample", (-0.6, 0, 0), (1.35, 0.95, 2.7), rubber, 0.24)
    # Raised molded ribs are geometry; fine stippling uses the shared height map.
    for z in (-0.72, -0.24, 0.24, 0.72):
        block("Molded Grip Rib", (-0.6, -0.47, z), (1.02, 0.17, 0.13), rubber, 0.055)
    block("Hard Polymer Sample", (1.05, 0.12, -0.3), (1.05, 0.8, 2.1), plastic, 0.17)
    world = bpy.data.worlds.new("Grip Studio World")
    world.use_nodes = True
    scene.world = world
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.14, 0.17, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, position, power, size in [
        ("Key", (0, -4, 5), 1100, 3),
        ("Fill", (-4, -2, 1), 550, 3),
        ("Rim", (3, 2, 3), 1300, 2),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.shape, data.size = power, "DISK", size
    camera = bpy.data.objects.new("Grip Camera", bpy.data.cameras.new("Grip Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (3.4, -6.5, 3)
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 4.25
    scene.render.engine = "CYCLES"
    scene.cycles.samples, scene.cycles.use_denoising = 64, True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "textured_grip_preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.data.texts.load(str(directory / "textured_grip.py"))
    bpy.data.images[DETAIL_IMAGE].filepath = "//textures/molded_grip_height.png"
    sys.path.insert(0, str(directory.parent))
    from real_scale_utils import resize_studio
    resize_studio(scene, body, 0.2 if "Grip" in body.name else 0.28)
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "textured_grip.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--plastic", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.preview:
        make_preview(Path(__file__).resolve().parent, args.render)
    else:
        targets = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not targets:
            raise RuntimeError("Select a mesh before running this script.")
        mat = make_material(args.plastic)
        for obj in targets:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
    print(f"Created textured grip material; Blender {bpy.app.version_string}")


if __name__ == "__main__":
    main()
