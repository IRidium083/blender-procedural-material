"""Blender 5.2: procedural chipped paint / oxidized steel, no image textures.

Run in Blender's Text Editor to apply to selected meshes (or the active mesh).
CLI example:
  blender -b test.blend -P worn_painted_metal.py -- --preview --render
Preview saves worn_painted_metal.blend beside this script; test.blend is untouched.
Both Cycles and Eevee are supported. AO-based wear/dust is most accurate in
Cycles; Eevee uses screen-space AO, so off-screen geometry can change masks.
Edge Width and Dust Distance are scene-space distances; use applied scale and
outward-facing normals on solid meshes. Dust requires actual concave geometry.
"""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector

NAME = "Worn Painted Metal"


def make_material():
    material = bpy.data.materials.get(NAME) or bpy.data.materials.new(NAME)
    material.use_nodes = True
    material.diffuse_color = (0.025, 0.22, 0.18, 1)
    tree = material.node_tree
    tree.nodes.clear()
    group = bpy.data.node_groups.new(NAME + " • Surface", "ShaderNodeTree")

    def socket(name, kind, value, low=None, high=None):
        s = group.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
        s.default_value = value
        if low is not None:
            s.min_value, s.max_value = low, high
        return s

    socket("Paint Color", "NodeSocketColor", (0.025, 0.22, 0.18, 1))
    socket("Metal Color", "NodeSocketColor", (0.22, 0.26, 0.29, 1))
    socket("Rust Color", "NodeSocketColor", (0.16, 0.043, 0.012, 1))
    socket("Wear", "NodeSocketFloat", 0.48, 0, 1)
    socket("Pattern Scale", "NodeSocketFloat", 1.0, 0.01, 100)
    socket("Paint Roughness", "NodeSocketFloat", 0.38, 0, 1)
    socket("Relief", "NodeSocketFloat", 0.025, 0, 0.2)
    socket("Edge Wear", "NodeSocketFloat", 0.85, 0, 1)
    socket("Edge Width", "NodeSocketFloat", 0.16, 0.001, 10)
    socket("Dust Amount", "NodeSocketFloat", 0.8, 0, 1)
    socket("Dust Distance", "NodeSocketFloat", 0.3, 0.001, 10)
    socket("Dust Color", "NodeSocketColor", (0.24, 0.18, 0.105, 1))
    socket("Scratch Amount", "NodeSocketFloat", 0.85, 0, 1)
    socket("Scratch Scale", "NodeSocketFloat", 1.0, 0.01, 20)
    socket("Scratch Depth", "NodeSocketFloat", 0.009, 0, 0.1)
    group.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    def node(kind, label, x, y):
        n = group.nodes.new(kind)
        n.label = n.name = label
        n.location = (x, y)
        n.width = 190
        return n

    def link(source, output, target, input_):
        group.links.new(source.outputs[output], target.inputs[input_])

    def math_node(label, operation, x, y, a=None, b=None):
        n = node("ShaderNodeMath", label, x, y)
        n.operation = operation
        for i, v in enumerate((a, b)):
            if v is not None:
                n.inputs[i].default_value = v
        return n

    def noise(label, scale, detail, x, y, source):
        n = node("ShaderNodeTexNoise", label, x, y)
        n.noise_dimensions = "3D"
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = 0.72
        link(source, "Vector", n, "Vector")
        return n

    def ramp(label, source, stops, x, y):
        n = node("ShaderNodeValToRGB", label, x, y)
        r = n.color_ramp
        r.interpolation = "LINEAR"
        for i, (pos, color) in enumerate(stops):
            e = r.elements[i] if i < 2 else r.elements.new(pos)
            e.position, e.color = pos, color
        link(source, 0, n, "Fac")
        return n

    def mix(label, factor, color_a, color_b, x, y):
        n = node("ShaderNodeMixRGB", label, x, y)
        link(factor, 0, n, 0)
        for i, value in enumerate((color_a, color_b), 1):
            if isinstance(value, tuple) and len(value) == 2:
                link(value[0], value[1], n, i)
            else:
                n.inputs[i].default_value = value
        return n

    controls = node("NodeGroupInput", "Material Controls", -1450, 650)
    coords = node("ShaderNodeTexCoord", "Object Space • no UVs needed", -1450, 150)
    scale = node("ShaderNodeVectorMath", "Overall Pattern Scale", -1200, 150)
    scale.operation = "SCALE"
    link(coords, "Object", scale, 0)
    link(controls, "Pattern Scale", scale, "Scale")
    chips = noise("Fractal Paint Chips", 3.8, 5, -950, 450, scale)
    grain = noise("Steel Pitting / Paint Grain", 145, 2, -950, -100, scale)
    stretch = node("ShaderNodeVectorMath", "Directional Scratch Stretch", -950, -500)
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1.2, 32, 32)
    scratch_scale = node("ShaderNodeVectorMath", "Scratch Frequency", -1450, -1700)
    scratch_scale.operation = "SCALE"
    link(scale, "Vector", scratch_scale, 0)
    link(controls, "Scratch Scale", scratch_scale, "Scale")
    link(scratch_scale, "Vector", stretch, 0)
    scratches = noise("Fine Abrasion", 1, 2, -700, -500, stretch)
    scratch_mask = ramp("Sparse Hairline Scratches", scratches,
                        [(0.63, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))], -450, -500)
    rotation = node("ShaderNodeMapping", "Crossing Scratch Direction", -1200, -1700)
    rotation.inputs["Rotation"].default_value = (0.45, 0.65, 0.55)
    link(scratch_scale, "Vector", rotation, "Vector")
    cross_stretch = node("ShaderNodeVectorMath", "Cross Scratch Stretch", -950, -1700)
    cross_stretch.operation = "MULTIPLY"
    cross_stretch.inputs[1].default_value = (1.8, 45, 45)
    link(rotation, "Vector", cross_stretch, 0)
    cross_noise = noise("Cross Abrasion", 1, 2, -700, -1700, cross_stretch)
    cross_mask = ramp("Sparse Crossing Scratches", cross_noise,
                      [(0.65, (0, 0, 0, 1)), (0.70, (1, 1, 1, 1))], -450, -1700)
    combined_scratches = math_node("Two Scratch Directions", "MAXIMUM", -200, -1700)
    link(scratch_mask, "Color", combined_scratches, 0)
    link(cross_mask, "Color", combined_scratches, 1)
    threshold = math_node("Wear Threshold", "SUBTRACT", -950, 800, 1.05)
    link(controls, "Wear", threshold, 1)
    difference = math_node("Noise minus Threshold", "SUBTRACT", -700, 450)
    link(chips, "Fac", difference, 0)
    link(threshold, 0, difference, 1)
    amplify = math_node("Sharp Chip Borders", "MULTIPLY", -450, 450, b=28)
    link(difference, 0, amplify, 0)
    exposed = math_node("Exposed Steel Mask", "ADD", -200, 450, b=0.5)
    exposed.use_clamp = True
    link(amplify, 0, exposed, 0)
    undercoat = math_node("Oxidized Chip Border", "ADD", -200, 180, b=1.25)
    undercoat.use_clamp = True
    link(amplify, 0, undercoat, 0)
    abrasion = math_node("Independent Scratch Amount", "MULTIPLY", -200, -450)
    link(combined_scratches, 0, abrasion, 0)
    link(controls, "Scratch Amount", abrasion, 1)
    # Inside AO probes convex edges; ordinary AO probes sheltered creases.
    # Avoid Pointiness/Bevel shader nodes, which are unsupported in Eevee.
    geometry = node("ShaderNodeNewGeometry", "Unbumped Geometry Normal", -1450, -950)

    def occlusion_mask(label, inside, distance_socket, x, y):
        ao = node("ShaderNodeAmbientOcclusion", label, x, y)
        ao.inside = inside
        ao.only_local = False
        ao.samples = 16
        link(controls, distance_socket, ao, "Distance")
        link(geometry, "Normal", ao, "Normal")
        mask = math_node(label + " Mask", "SUBTRACT", x + 240, y, 1)
        link(ao, "AO", mask, 1)
        return mask

    convex = occlusion_mask("Convex Edge AO", True, "Edge Width", -1200, -900)
    concave = occlusion_mask("Concave Crease AO", False, "Dust Distance", -1200, -1250)
    edge_gain = math_node("Edge Contrast", "MULTIPLY", -700, -900, b=3.5)
    edge_gain.use_clamp = True
    link(convex, 0, edge_gain, 0)
    breakup = ramp("Uneven Edge Abrasion", chips,
                   [(0.2, (0.35, 0.35, 0.35, 1)), (0.7, (1, 1, 1, 1))], -700, -700)
    broken_edge = math_node("Break Up Edge Wear", "MULTIPLY", -450, -900)
    link(edge_gain, 0, broken_edge, 0)
    link(breakup, 0, broken_edge, 1)
    edge_amount = math_node("Edge Wear Amount", "MULTIPLY", -200, -900)
    link(broken_edge, 0, edge_amount, 0)
    link(controls, "Edge Wear", edge_amount, 1)
    chips_scratches = math_node("Chips plus Scratches", "MAXIMUM", 50, 650)
    link(exposed, 0, chips_scratches, 0)
    link(abrasion, 0, chips_scratches, 1)
    bare = math_node("Include Convex Edge Wear", "MAXIMUM", 300, 650)
    link(chips_scratches, 0, bare, 0)
    link(edge_amount, 0, bare, 1)
    cavity_gain = math_node("Crease Dust Concentration", "MULTIPLY", -700, -1250, b=2.5)
    cavity_gain.use_clamp = True
    link(concave, 0, cavity_gain, 0)
    dusty_noise = math_node("Uneven Dust Accumulation", "MULTIPLY", -450, -1250)
    link(cavity_gain, 0, dusty_noise, 0)
    link(breakup, 0, dusty_noise, 1)
    dust = math_node("Dust Coverage", "MULTIPLY", -200, -1250)
    link(dusty_noise, 0, dust, 0)
    link(controls, "Dust Amount", dust, 1)
    edge = mix("Paint / Rust Border", undercoat, (controls, "Paint Color"),
               (controls, "Rust Color"), 50, 150)
    color = mix("Reveal Steel", bare, (edge, 0), (controls, "Metal Color"), 300, 300)
    variation = ramp("Subtle Surface Mottling", grain,
                     [(0.2, (0.55, 0.55, 0.55, 1)), (0.8, (1, 1, 1, 1))], 50, -150)
    tint = node("ShaderNodeMixRGB", "Weathered Color Variation", 550, 300)
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 0.45
    link(color, 0, tint, 1)
    link(variation, 0, tint, 2)
    rough = mix("Paint / Steel Roughness", bare, (controls, "Paint Roughness"),
                (0.58, 0.58, 0.58, 1), 550, 0)
    micro = node("ShaderNodeBump", "Fine Surface Grain", 300, -400)
    micro.inputs["Strength"].default_value = 0.22
    micro.inputs["Distance"].default_value = 0.008
    link(grain, "Fac", micro, "Height")
    relief = node("ShaderNodeBump", "Recessed Chips and Scratches", 550, -350)
    relief.invert = True
    relief.inputs["Strength"].default_value = 0.32
    link(controls, "Relief", relief, "Distance")
    link(bare, 0, relief, "Height")
    link(micro, "Normal", relief, "Normal")
    scratch_bump = node("ShaderNodeBump", "Incised Surface Scratches", 550, -700)
    scratch_bump.invert = True
    scratch_bump.inputs["Strength"].default_value = 0.3
    link(controls, "Scratch Depth", scratch_bump, "Distance")
    link(abrasion, 0, scratch_bump, "Height")
    link(relief, "Normal", scratch_bump, "Normal")
    dust_color = mix("Dust over Painted Metal", dust, (tint, 0),
                     (controls, "Dust Color"), 850, 650)
    dust_rough = mix("Matte Dust Roughness", dust, (rough, 0),
                     (0.92, 0.92, 0.92, 1), 850, 100)
    dust_metal = mix("Dust Is Nonmetallic", dust, (bare, 0),
                     (0, 0, 0, 1), 850, -150)
    shader = node("ShaderNodeBsdfPrincipled", "Paint over Steel", 1150, 350)
    link(dust_color, 0, shader, "Base Color")
    link(dust_metal, 0, shader, "Metallic")
    link(dust_rough, 0, shader, "Roughness")
    link(scratch_bump, "Normal", shader, "Normal")
    output = node("NodeGroupOutput", "Surface Output", 1450, 350)
    link(shader, "BSDF", output, "Shader")
    instance = tree.nodes.new("ShaderNodeGroup")
    instance.node_tree = group
    instance.width = 290
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (380, 0)
    tree.links.new(instance.outputs["Shader"], output.inputs["Surface"])
    return material


def preview(scene, target, directory, render):
    if not target.modifiers.get("Preview Rounded Edges"):
        bevel = target.modifiers.new("Preview Rounded Edges", "BEVEL")
        bevel.width, bevel.segments = 0.09, 5
    # A separate solid rail retains genuine 90-degree edges (no bevel modifier),
    # next to the rounded cube edges, to make the convex wear easy to compare.
    rail = bpy.data.objects.get("Preview Sharp Edge Rail")
    if rail is None:
        bpy.ops.mesh.primitive_cube_add(size=2)
        rail = bpy.context.object
        rail.name = "Preview Sharp Edge Rail"
        rail.scale = (0.78, 0.22, 0.16)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rail.location = target.location + Vector((0, 0, 1.16))
    rail.data.materials.clear()
    rail.data.materials.append(target.active_material)
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get("Background").inputs[0].default_value = (0.15, 0.18, 0.23, 1)
    scene.world.node_tree.nodes.get("Background").inputs[1].default_value = 0.45
    for name, location, power, size in [
        ("Preview Key", (3, -4, 5), 950, 4),
        ("Preview Fill", (-4, -2, 2), 700, 3),
        ("Preview Rim", (2, 3, 4), 1100, 3),
    ]:
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
            scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (target.location - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.data.energy, obj.data.shape, obj.data.size = power, "DISK", size
    if scene.camera:
        scene.camera.location = target.location + Vector((4, -6, 3.5))
        scene.camera.rotation_euler = (target.location - scene.camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera.data.type = "ORTHO"
        scene.camera.data.ortho_scale = 3.9
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "worn_painted_metal_preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "worn_painted_metal.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


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
        preview(bpy.context.scene, targets[0], Path(__file__).resolve().parent, args.render)
    print(f"Applied {NAME} to {len(targets)} mesh(es), Blender {bpy.app.version_string}")


if __name__ == "__main__":
    main()
