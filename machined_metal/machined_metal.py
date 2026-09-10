"""Image-assisted machined metal for Blender 5.2; apply to selected meshes.

Object-space parallel tool marks, anisotropic reflections and uneven roughness.
Run with --preview --render to save a studio sample beside this script.
"""
import argparse
from pathlib import Path
import sys

import bpy

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parent))
from preview_utils import setup_studio

NAME = "Machined Metal"


def make_material():
    material = bpy.data.materials.get(NAME) or bpy.data.materials.get("Machined Aluminum") or bpy.data.materials.new(NAME)
    material.name = NAME
    material.use_nodes = True
    material.diffuse_color = (0.72, 0.76, 0.8, 1)
    tree = material.node_tree
    tree.nodes.clear()
    group = bpy.data.node_groups.new(NAME + " - Surface", "ShaderNodeTree")

    def control(name, kind, value, low=None, high=None):
        socket = group.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
        socket.default_value = value
        if low is not None:
            socket.min_value, socket.max_value = low, high

    control("Metal Color", "NodeSocketColor", (0.72, 0.76, 0.8, 1))
    control("Roughness", "NodeSocketFloat", 0.28, 0, 1)
    control("Roughness Variation", "NodeSocketFloat", 0.18, 0, 1)
    control("Anisotropy", "NodeSocketFloat", 0.65, 0, 1)
    control("Tool Mark Scale", "NodeSocketFloat", 1.5, 0.01, 100)
    control("Mark Color Variation", "NodeSocketFloat", 0.12, 0, 1)
    control("Anisotropy Variation", "NodeSocketFloat", 0.3, 0, 1)
    control("Machining Rotation", "NodeSocketFloat", 0, -3.141593, 3.141593)
    group.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    def node(kind, name, x, y):
        n = group.nodes.new(kind)
        n.name = n.label = name
        n.location = (x, y)
        n.width = 200
        return n

    def link(a, output, b, input_):
        group.links.new(a.outputs[output], b.inputs[input_])

    controls = node("NodeGroupInput", "Material Controls", -1100, 600)
    coords = node("ShaderNodeTexCoord", "Object Coordinates", -1100, 100)
    rotation = node("ShaderNodeCombineXYZ", "Machining Angle", -1100, -200)
    link(controls, "Machining Rotation", rotation, "Z")
    mapping = node("ShaderNodeMapping", "Tool Orientation", -850, 100)
    link(coords, "Object", mapping, "Vector")
    link(rotation, "Vector", mapping, "Rotation")
    frequency = node("ShaderNodeVectorMath", "Texture Tiling", -650, 150)
    frequency.operation = "SCALE"
    link(mapping, "Vector", frequency, 0)
    link(controls, "Tool Mark Scale", frequency, "Scale")
    texture_path = DIRECTORY / "textures" / "machining_height.png"
    image = bpy.data.images.load(str(texture_path), check_existing=True)
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    detail = node("ShaderNodeTexImage", "Machining Microdetail", -400, 150)
    detail.image = image
    detail.projection = "BOX"
    detail.projection_blend = 0.2
    detail.extension = "REPEAT"
    link(frequency, "Vector", detail, "Vector")
    centered = node("ShaderNodeMath", "Center Finish Noise", -350, -200)
    centered.operation = "SUBTRACT"
    centered.inputs[1].default_value = 0.5
    link(detail, "Color", centered, 0)
    amount = node("ShaderNodeMath", "Finish Variation Amount", -100, -200)
    amount.operation = "MULTIPLY"
    link(centered, 0, amount, 0)
    link(controls, "Roughness Variation", amount, 1)
    roughness = node("ShaderNodeMath", "Metal Roughness", 150, -100)
    roughness.operation = "ADD"
    roughness.use_clamp = True
    link(amount, 0, roughness, 0)
    link(controls, "Roughness", roughness, 1)
    color = node("ShaderNodeMixRGB", "Subtle Machining Color", 150, 650)
    color.blend_type = "MULTIPLY"
    link(controls, "Mark Color Variation", color, 0)
    link(controls, "Metal Color", color, 1)
    link(detail, "Color", color, 2)
    anis_amount = node("ShaderNodeMath", "Machining Anisotropy Variation", -100, 400)
    anis_amount.operation = "MULTIPLY"
    link(centered, 0, anis_amount, 0)
    link(controls, "Anisotropy Variation", anis_amount, 1)
    anis = node("ShaderNodeMath", "Varied Anisotropy", 150, 400)
    anis.operation = "ADD"
    anis.use_clamp = True
    link(controls, "Anisotropy", anis, 0)
    link(anis_amount, 0, anis, 1)
    # Rotate the local groove direction with the inverse coordinate rotation.
    angle = node("ShaderNodeMath", "Inverse Tool Angle", -850, -500)
    angle.operation = "MULTIPLY"
    angle.inputs[1].default_value = -1
    link(controls, "Machining Rotation", angle, 0)
    tangent = node("ShaderNodeVectorRotate", "Local Tool Direction", -600, -500)
    tangent.rotation_type = "Z_AXIS"
    tangent.inputs["Vector"].default_value = (0, 1, 0)
    link(angle, 0, tangent, "Angle")
    world = node("ShaderNodeVectorTransform", "World Tool Direction", -350, -500)
    world.vector_type = "VECTOR"
    world.convert_from = "OBJECT"
    world.convert_to = "WORLD"
    link(tangent, "Vector", world, "Vector")
    geometry = node("ShaderNodeNewGeometry", "Surface Geometry", -850, -800)
    across = node("ShaderNodeVectorMath", "Across Tool Direction", -600, -800)
    across.operation = "CROSS_PRODUCT"
    link(geometry, "Normal", across, 0)
    link(world, "Vector", across, 1)
    projected = node("ShaderNodeVectorMath", "Surface Tool Direction", -350, -800)
    projected.operation = "CROSS_PRODUCT"
    link(across, "Vector", projected, 0)
    link(geometry, "Normal", projected, 1)
    length = node("ShaderNodeVectorMath", "Tangent Length", -100, -800)
    length.operation = "LENGTH"
    link(projected, "Vector", length, 0)
    parallel = node("ShaderNodeMath", "Parallel Direction Fallback", 150, -800)
    parallel.operation = "LESS_THAN"
    parallel.inputs[1].default_value = 0.01
    link(length, "Value", parallel, 0)
    fallback = node("ShaderNodeVectorMath", "Fallback Surface Direction", -350, -1050)
    fallback.operation = "CROSS_PRODUCT"
    fallback.inputs[1].default_value = (0, 0, 1)
    link(geometry, "Normal", fallback, 0)
    select = node("ShaderNodeMixRGB", "Stable Surface Tangent", 400, -800)
    link(parallel, 0, select, 0)
    link(projected, "Vector", select, 1)
    link(fallback, "Vector", select, 2)
    shader = node("ShaderNodeBsdfPrincipled", "Solid Machined Metal", 450, 400)
    shader.inputs["Metallic"].default_value = 1
    link(color, "Color", shader, "Base Color")
    link(roughness, 0, shader, "Roughness")
    link(anis, 0, shader, "Anisotropic")
    link(select, "Color", shader, "Tangent")
    output = node("NodeGroupOutput", "Surface Output", 800, 400)
    link(shader, "BSDF", output, "Shader")
    instance = tree.nodes.new("ShaderNodeGroup")
    instance.node_tree = group
    instance.width = 300
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    tree.links.new(instance.outputs["Shader"], output.inputs["Surface"])
    return material


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    targets = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not targets and bpy.context.object and bpy.context.object.type == "MESH":
        targets = [bpy.context.object]
    if not targets:
        raise RuntimeError("Select a mesh before running this script.")
    material = make_material()
    for obj in targets:
        if obj.data.materials:
            obj.data.materials[obj.active_material_index] = material
        else:
            obj.data.materials.append(material)
    if args.preview:
        target = targets[0]
        bevel = target.modifiers.get("Preview Rounded Edges") or target.modifiers.new("Preview Rounded Edges", "BEVEL")
        bevel.width, bevel.segments = 0.08, 5
        setup_studio(bpy.context.scene, target)
        scene = bpy.context.scene
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.45, 0.45, 1)
        scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(DIRECTORY / "machined_metal_preview.png")
        for old_text in list(bpy.data.texts):
            if old_text.name == "machined_aluminum.py":
                bpy.data.texts.remove(old_text)
        text = bpy.data.texts.get(Path(__file__).name) or bpy.data.texts.new(Path(__file__).name)
        text.clear()
        text.write(Path(__file__).read_text(encoding="utf-8"))
        text.filepath = str(Path(__file__).resolve())
        image = bpy.data.images.get("machining_height.png")
        if image:
            image.filepath = "//textures/machining_height.png"
        bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY / "machined_metal.blend"))
        if args.render:
            bpy.ops.render.render(write_still=True)
    print(f"Applied {NAME} to {len(targets)} mesh(es)")


if __name__ == "__main__":
    main()
