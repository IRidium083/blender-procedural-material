"""Procedural machined aluminum for Blender 5.2; apply to selected meshes.

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

NAME = "Machined Aluminum"


def make_material():
    material = bpy.data.materials.get(NAME) or bpy.data.materials.new(NAME)
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

    control("Aluminum Color", "NodeSocketColor", (0.72, 0.76, 0.8, 1))
    control("Roughness", "NodeSocketFloat", 0.28, 0, 1)
    control("Roughness Variation", "NodeSocketFloat", 0.04, 0, 1)
    control("Anisotropy", "NodeSocketFloat", 0.65, 0, 1)
    control("Tool Mark Scale", "NodeSocketFloat", 22, 1, 1000)
    control("Tool Mark Depth", "NodeSocketFloat", 0.001, 0, 0.02)
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
    wave = node("ShaderNodeTexWave", "Parallel Milling Passes", -600, 150)
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.wave_profile = "SIN"
    wave.inputs["Distortion"].default_value = 0.15
    wave.inputs["Detail Scale"].default_value = 0.6
    link(mapping, "Vector", wave, "Vector")
    link(controls, "Tool Mark Scale", wave, "Scale")
    noise = node("ShaderNodeTexNoise", "Subtle Finish Variation", -600, -200)
    noise.inputs["Scale"].default_value = 5
    noise.inputs["Detail"].default_value = 2
    link(mapping, "Vector", noise, "Vector")
    centered = node("ShaderNodeMath", "Center Finish Noise", -350, -200)
    centered.operation = "SUBTRACT"
    centered.inputs[1].default_value = 0.5
    link(noise, "Fac", centered, 0)
    amount = node("ShaderNodeMath", "Finish Variation Amount", -100, -200)
    amount.operation = "MULTIPLY"
    link(centered, 0, amount, 0)
    link(controls, "Roughness Variation", amount, 1)
    roughness = node("ShaderNodeMath", "Aluminum Roughness", 150, -100)
    roughness.operation = "ADD"
    roughness.use_clamp = True
    link(amount, 0, roughness, 0)
    link(controls, "Roughness", roughness, 1)
    bump = node("ShaderNodeBump", "Shallow Tool Grooves", -100, 150)
    bump.inputs["Strength"].default_value = 0.35
    link(wave, "Fac", bump, "Height")
    link(controls, "Tool Mark Depth", bump, "Distance")
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
    shader = node("ShaderNodeBsdfPrincipled", "Solid Machined Aluminum", 450, 400)
    shader.inputs["Metallic"].default_value = 1
    link(controls, "Aluminum Color", shader, "Base Color")
    link(roughness, 0, shader, "Roughness")
    link(controls, "Anisotropy", shader, "Anisotropic")
    link(world, "Vector", shader, "Tangent")
    link(bump, "Normal", shader, "Normal")
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
        scene.render.filepath = str(DIRECTORY / "machined_aluminum_preview.png")
        text = bpy.data.texts.get(Path(__file__).name) or bpy.data.texts.new(Path(__file__).name)
        text.clear()
        text.write(Path(__file__).read_text(encoding="utf-8"))
        text.filepath = str(Path(__file__).resolve())
        bpy.ops.wm.save_as_mainfile(filepath=str(DIRECTORY / "machined_aluminum.blend"))
        if args.render:
            bpy.ops.render.render(write_still=True)
    print(f"Applied {NAME} to {len(targets)} mesh(es)")


if __name__ == "__main__":
    main()
