"""Unified Metal v1, Blender 5.2. Native menu presets, no add-on required.
Run with selected meshes, or CLI --preview --render. All surface sizes are mm.
Coatings, plating removal and substrate reveal are intentionally deferred.
"""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

VERSION = "1.0"
PREFIX = "UM v1 | "
IMAGE_NAME = "UM Oil Smears"
METALS = ["Steel", "Aluminum", "Bronze", "Copper", "Custom"]
FINISHES = ["Polished", "Brushed", "Cast", "Stonewashed", "Machined", "Custom"]


def oil_image():
    image = bpy.data.images.get(IMAGE_NAME)
    if image and image.packed_file:
        return image
    relative = Path("textures/oil_smear_mask.png")
    candidates = [Path(__file__).resolve().parent / relative]
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).parent / relative)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError("Missing textures/oil_smear_mask.png; keep it beside unified_metal.py or use the packed .blend.")
    image = bpy.data.images.load(str(path), check_existing=True)
    image.name = IMAGE_NAME
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


class Graph:
    """Small builder; all module boundaries are ordinary shader-group sockets."""
    def __init__(self, name):
        self.tree = bpy.data.node_groups.new(PREFIX + name, "ShaderNodeTree")
        self.tree["um_version"] = VERSION
        self.specs = []
        self.gin = self.node("NodeGroupInput", "Inputs")
        self.gout = self.node("NodeGroupOutput", "Outputs")

    def node(self, kind, name):
        n = self.tree.nodes.new(kind)
        n.name = n.label = name
        n.width = 210
        return n

    def set(self, target, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, target)
        else:
            target.default_value = value

    def input(self, name, kind="Float", default=None, limits=None, panel=None):
        s = self.tree.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocket" + kind)
        if default is not None and kind != "Menu":
            s.default_value = default
        if limits:
            s.min_value, s.max_value = limits
        if panel:
            self.tree.interface.move_to_parent(s, panel, len(panel.interface_items))
        self.specs.append((name, kind, default, limits))
        return self.gin.outputs[name]

    def output(self, name, value, kind="Float"):
        self.tree.interface.new_socket(name=name, in_out="OUTPUT", socket_type="NodeSocket" + kind)
        self.set(self.gout.inputs[name], value)

    def math(self, op, a, b=0, name=None, clamp=False):
        n = self.node("ShaderNodeMath", name or op.title())
        n.operation, n.use_clamp = op, clamp
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        if op == "COMPARE":
            n.inputs[2].default_value = 0.1
        return n.outputs[0]

    def vector(self, op, a, b):
        n = self.node("ShaderNodeVectorMath", op.title())
        n.operation = op
        self.set(n.inputs[0], a)
        self.set(n.inputs["Scale"] if op == "SCALE" else n.inputs[1], b)
        return n.outputs[0]

    def mix(self, factor, a, b, name="Blend"):
        n = self.node("ShaderNodeMixRGB", name)
        self.set(n.inputs[0], factor)
        for i, value in enumerate((a, b), 1):
            if isinstance(value, (int, float)):
                value = (value, value, value, 1)
            self.set(n.inputs[i], value)
        return n.outputs[0]

    def menu(self, socket, names, values=None, kind="INT"):
        n = self.node("GeometryNodeMenuSwitch", socket.name + " Presets")
        n.data_type = kind
        n.enum_items.clear()
        for name in names:
            n.enum_items.new(name=name)
        self.set(n.inputs["Menu"], socket)
        for i, value in enumerate(values if values is not None else range(len(names))):
            self.set(n.inputs[i + 1], value)
        return n.outputs[0]

    def pick(self, index, values, name):
        # Index Switch is not registered for ShaderNodeTree in the installed 5.2.
        # Resolve scalar preset channels with exact integer comparisons instead.
        terms = [self.math("MULTIPLY", self.math("COMPARE", index, i), v)
                 for i, v in enumerate(values)]
        result = terms[0]
        for term in terms[1:]:
            result = self.math("ADD", result, term, name)
        return result

    def noise(self, coords, scale, detail=2, name="Noise"):
        n = self.node("ShaderNodeTexNoise", name)
        self.set(n.inputs["Vector"], coords)
        self.set(n.inputs["Scale"], scale)
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = 0.65
        return n.outputs["Fac"]

    def ramp(self, value, low, high, name):
        n = self.node("ShaderNodeValToRGB", name)
        n.color_ramp.elements[0].position = low
        n.color_ramp.elements[1].position = high
        self.set(n.inputs["Fac"], value)
        return n.outputs["Color"]

    def instance(self, module):
        n = self.node("ShaderNodeGroup", module.tree.name)
        n.node_tree = module.tree
        n.width = 280
        return n

    def layout(self):
        depth = {n: 0 for n in self.tree.nodes}
        for _ in range(len(depth)):
            changed = False
            for edge in self.tree.links:
                d = depth[edge.from_node] + 1
                if depth[edge.to_node] < d:
                    depth[edge.to_node], changed = d, True
            if not changed:
                break
        rows = {}
        for n, d in depth.items():
            row = rows.get(d, 0)
            n.location = (d * 320, -row * 360)
            rows[d] = row + 1


def base_module():
    g = Graph("1 Base Metal")
    metal = g.input("Base Metal", "Menu")
    custom = g.input("Custom Metal Color", "Color", (0.55, 0.58, 0.6, 1))
    color = g.menu(metal, METALS, [
        (0.55, 0.58, 0.6, 1), (0.83, 0.85, 0.88, 1),
        (0.55, 0.32, 0.12, 1), (0.90, 0.47, 0.28, 1), custom], "RGBA")
    g.output("Color", color, "Color")
    g.output("Metallic", 1)
    return g


def finish_module():
    g = Graph("2 Surface Finish")
    xyz = g.input("Coordinates mm", "Vector", (0, 0, 0))
    finish = g.menu(g.input("Finish", "Menu"), FINISHES)
    custom_size = g.input("Custom Grain mm", default=0.5, limits=(0.01, 10))
    size = g.menu(g.input("Texture Size", "Menu"), ["Fine", "Medium", "Coarse", "Custom"],
                  [0.15, 0.5, 1.2, custom_size], "FLOAT")
    cr = g.input("Custom Roughness", default=0.35, limits=(0.02, 1))
    cd = g.input("Custom Relief mm", default=0.008, limits=(0, 0.5))
    ca = g.input("Custom Anisotropy", default=0.0, limits=(0, 1))
    direction = g.input("Direction Rotation", "Vector", (0, 0, 0))
    seed = g.input("Finish Seed", default=0, limits=(0, 1000))
    mapping = g.node("ShaderNodeMapping", "Finish Orientation")
    g.set(mapping.inputs["Vector"], xyz)
    g.set(mapping.inputs["Rotation"], direction)
    v = g.vector("SCALE", mapping.outputs["Vector"], g.math("DIVIDE", 1, size))
    v = g.vector("ADD", v, g.vector("SCALE", (0.37, 0.61, 0.83), seed))
    isotropic = g.noise(v, 1, 4, "Cast Grain")
    brushed = g.noise(g.vector("MULTIPLY", v, (0.03, 3, 3)), 1, 2, "Straight Brush Lines")
    machined = g.noise(g.vector("MULTIPLY", v, (0.02, 0.02, 5)), 1, 2, "Turning Lines around Z")
    stone = g.noise(v, 1.7, 3, "Stonewash Dents")
    stone = g.math("POWER", stone, 2)
    height = g.pick(finish, [isotropic, brushed, isotropic, stone, machined, isotropic], "Finish Height")
    depth = g.pick(finish, [0.0005, 0.003, 0.025, 0.009, 0.002, cd], "Finish Relief mm")
    rough = g.pick(finish, [0.12, 0.32, 0.68, 0.48, 0.22, cr], "Preset Roughness")
    rough = g.math("ADD", rough, g.math("MULTIPLY", g.math("SUBTRACT", height, 0.5), 0.1), clamp=True)
    tangent = g.node("ShaderNodeVectorRotate", "Brushing Tangent")
    tangent.rotation_type = "EULER_XYZ"
    tangent.inputs["Vector"].default_value = (1, 0, 0)
    g.set(tangent.inputs["Rotation"], g.vector("SCALE", direction, -1))
    g.output("Roughness", rough)
    g.output("Height mm", g.math("MULTIPLY", height, depth))
    g.output("Anisotropy", g.pick(finish, [0, 0.65, 0, 0.15, 0.4, ca], "Finish Anisotropy"))
    g.output("Tangent", tangent.outputs["Vector"], "Vector")
    return g


def imperfections_module(image):
    g = Graph("3 Imperfections")
    xyz = g.input("Coordinates mm", "Vector", (0, 0, 0))
    units = g.input("Scene Unit m", default=1, limits=(0.000001, 1000))
    rough = g.input("Roughness", default=0.3)
    height = g.input("Height mm", default=0)
    custom_wear = g.input("Custom Wear", default=0.25, limits=(0, 1))
    wear = g.menu(g.input("Wear Level", "Menu"), ["None", "Light", "Moderate", "Heavy", "Custom"],
                  [0, 0.2, 0.5, 0.85, custom_wear], "FLOAT")
    width = g.input("Wear Width mm", default=0.6, limits=(0.01, 20))
    scratches = g.input("Scratches", "Bool", True)
    scratch_amount = g.input("Scratch Amount", default=0.15, limits=(0, 1))
    scratch_width = g.input("Scratch Width mm", default=0.08, limits=(0.005, 2))
    scratch_depth = g.input("Scratch Depth mm", default=0.003, limits=(0, 0.1))
    dust_enabled = g.input("Dust", "Bool", False)
    dust_amount = g.input("Dust Amount", default=0.3, limits=(0, 1))
    dust_color = g.input("Dust Color", "Color", (0.22, 0.17, 0.1, 1))
    dust_distance = g.input("Dust Spread mm", default=3, limits=(0.01, 100))
    oil_enabled = g.input("Oil", "Bool", False)
    oil_amount = g.input("Oil Amount", default=0.5, limits=(0, 1))
    oil_size = g.input("Oil Patch mm", default=30, limits=(0.1, 500))
    oil_tint = g.input("Oil Tint", "Color", (0.13, 0.075, 0.025, 1))
    seed = g.input("Imperfection Seed", default=7, limits=(0, 1000))
    mm_to_units = g.math("DIVIDE", 0.001, units)
    xyz = g.vector("ADD", xyz, g.vector("SCALE", (1.3, 2.7, 0.9), seed))
    breakup = g.noise(xyz, 0.4, 3, "Wear Distribution")
    geometry = g.node("ShaderNodeNewGeometry", "Unbumped Geometry")

    def ao(inside, distance, title):
        n = g.node("ShaderNodeAmbientOcclusion", title)
        n.inside, n.samples = inside, 16
        g.set(n.inputs["Normal"], geometry.outputs["Normal"])
        g.set(n.inputs["Distance"], g.math("MULTIPLY", distance, mm_to_units))
        return g.math("SUBTRACT", 1, n.outputs["AO"])

    convex = ao(True, width, "Convex Edge Wear")
    cavity = ao(False, dust_distance, "Cavity Deposit Mask")
    edge = g.math("MULTIPLY", g.math("MULTIPLY", convex, 4, clamp=True), breakup)
    edge = g.math("MULTIPLY", edge, wear)
    v = g.vector("MULTIPLY", g.vector("SCALE", xyz, g.math("DIVIDE", 1, scratch_width)), (0.015, 1, 1))
    scratch = g.ramp(g.noise(v, 1, 2, "Sparse Directional Abrasion"), 0.68, 0.74, "Scratch Mask")
    scratch = g.math("MULTIPLY", scratch, g.math("MULTIPLY", scratches, scratch_amount))
    new_height = g.math("MULTIPLY", height, g.math("SUBTRACT", 1, edge))
    new_height = g.math("SUBTRACT", new_height, g.math("MULTIPLY", scratch, scratch_depth))
    new_rough = g.math("ADD", g.math("SUBTRACT", rough, g.math("MULTIPLY", edge, 0.25)),
                       g.math("MULTIPLY", scratch, 0.15), clamp=True)
    normal = g.node("ShaderNodeSeparateXYZ", "Upward Surfaces")
    g.set(normal.inputs[0], geometry.outputs["Normal"])
    up = g.math("MAXIMUM", normal.outputs["Z"], 0)
    deposits = g.math("MAXIMUM", g.math("MULTIPLY", cavity, 2.8, clamp=True), g.math("MULTIPLY", up, 0.25))
    dust = g.math("MULTIPLY", deposits, g.math("MULTIPLY", dust_enabled, dust_amount))
    dust = g.math("MULTIPLY", dust, g.math("ADD", 0.5, g.math("MULTIPLY", breakup, 0.5)))
    tex = g.node("ShaderNodeTexImage", "Oil Smears - Only Image")
    tex.image, tex.projection, tex.projection_blend = image, "BOX", 0.3
    tex.extension = "REPEAT"
    g.set(tex.inputs["Vector"], g.vector("SCALE", xyz, g.math("DIVIDE", 1, oil_size)))
    oil = g.ramp(tex.outputs["Color"], 0.065, 0.48, "Oil Residue Mask")
    oil = g.math("MULTIPLY", oil, g.math("MULTIPLY", oil_enabled, oil_amount))
    for name, value in [("Roughness", new_rough), ("Height mm", new_height),
                        ("Wear Mask", edge), ("Scratch Mask", scratch), ("Dust Mask", dust), ("Oil Mask", oil)]:
        g.output(name, value)
    g.output("Dust Color", dust_color, "Color")
    g.output("Oil Tint", oil_tint, "Color")
    return g


def build_library():
    image = oil_image()
    base, finish, imperfections = base_module(), finish_module(), imperfections_module(image)
    g = Graph("Unified Metal")
    panels = {name: g.tree.interface.new_panel(name=name) for name in [
        "1 Base Metal", "2 Surface Finish", "3 Imperfections", "Scale and Debug"]}
    nodes = [g.instance(m) for m in (base, finish, imperfections)]
    internal = {"Coordinates mm", "Scene Unit m", "Roughness", "Height mm"}
    for module, instance, panel in zip((base, finish, imperfections), nodes, list(panels.values())[:3]):
        for name, kind, value, limits in module.specs:
            if name not in internal:
                g.set(instance.inputs[name], g.input(name, kind, value, limits, panel))
    units = g.input("Scene Unit m", default=bpy.context.scene.unit_settings.scale_length,
                    limits=(0.000001, 1000), panel=panels["Scale and Debug"])
    coords = g.node("ShaderNodeTexCoord", "Shared Object Coordinates")
    xyz = g.vector("SCALE", coords.outputs["Object"], g.math("MULTIPLY", units, 1000))
    b, f, imp = nodes
    g.set(f.inputs["Coordinates mm"], xyz)
    g.set(imp.inputs["Coordinates mm"], xyz)
    g.set(imp.inputs["Scene Unit m"], units)
    for name in ("Roughness", "Height mm"):
        g.set(imp.inputs[name], f.outputs[name])
    bump = g.node("ShaderNodeBump", "Combined Surface Relief")
    g.set(bump.inputs["Height"], imp.outputs["Height mm"])
    g.set(bump.inputs["Distance"], g.math("DIVIDE", 0.001, units))
    bump.inputs["Strength"].default_value = 0.5
    color = g.mix(imp.outputs["Oil Mask"], b.outputs["Color"], imp.outputs["Oil Tint"], "Oil Stains")
    rough = g.mix(imp.outputs["Oil Mask"], imp.outputs["Roughness"], 0.24, "Oil Smear Roughness")
    metal = g.node("ShaderNodeBsdfPrincipled", "Finished Metal")
    g.set(metal.inputs["Base Color"], color)
    g.set(metal.inputs["Metallic"], b.outputs["Metallic"])
    g.set(metal.inputs["Roughness"], rough)
    g.set(metal.inputs["Normal"], bump.outputs["Normal"])
    g.set(metal.inputs["Anisotropic"], f.outputs["Anisotropy"])
    g.set(metal.inputs["Tangent"], f.outputs["Tangent"])
    g.set(metal.inputs["Coat Weight"], imp.outputs["Oil Mask"])
    metal.inputs["Coat Roughness"].default_value = 0.12
    dust = g.node("ShaderNodeBsdfPrincipled", "Nonmetallic Dust")
    g.set(dust.inputs["Base Color"], imp.outputs["Dust Color"])
    dust.inputs["Metallic"].default_value = 0
    dust.inputs["Roughness"].default_value = 0.9
    g.set(dust.inputs["Normal"], bump.outputs["Normal"])
    blend = g.node("ShaderNodeMixShader", "Dust over Oiled Metal")
    g.set(blend.inputs[0], imp.outputs["Dust Mask"])
    g.set(blend.inputs[1], metal.outputs[0])
    g.set(blend.inputs[2], dust.outputs[0])
    debug_menu = g.input("View", "Menu", panel=panels["Scale and Debug"])
    debug = g.menu(debug_menu, ["Material", "Roughness", "Wear Mask", "Scratch Mask", "Dust Mask", "Oil Mask"],
                   [0, imp.outputs["Roughness"], imp.outputs["Wear Mask"], imp.outputs["Scratch Mask"],
                    imp.outputs["Dust Mask"], imp.outputs["Oil Mask"]], "FLOAT")
    # A negative sentinel distinguishes Material from a legitimately black mask.
    debug.node.inputs[1].default_value = -1
    emission = g.node("ShaderNodeEmission", "Mask Debug")
    g.set(emission.inputs["Color"], debug)
    switch = g.node("ShaderNodeMixShader", "Material or Debug")
    g.set(switch.inputs[0], g.math("LESS_THAN", debug, -0.5))
    g.set(switch.inputs[1], emission.outputs[0])
    g.set(switch.inputs[2], blend.outputs[0])
    g.output("Shader", switch.outputs[0], "Shader")
    for module in (base, finish, imperfections, g):
        module.layout()
    return g.tree


def make_material(name="Unified Metal", library=None, **presets):
    library = library or build_library()
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    n = mat.node_tree.nodes.new("ShaderNodeGroup")
    n.node_tree, n.name, n.width = library, "Unified Metal", 340
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (460, 0)
    mat.node_tree.links.new(n.outputs["Shader"], out.inputs["Surface"])
    settings = {"Base Metal": "Steel", "Finish": "Polished", "Texture Size": "Medium", "Wear Level": "Light", "View": "Material"}
    settings.update(presets)
    for key, value in settings.items():
        n.inputs[key].default_value = value
    mat["um_version"] = VERSION
    mat.asset_mark()
    mat.asset_data.description = "Modular metal with native metal/finish presets, mm scale, and independent wear, dust, and oil."
    return mat


def preview(directory, render):
    scene = bpy.data.scenes.new("Unified Metal - Preset Gallery")
    bpy.context.window.scene = scene
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1
    library = build_library()
    samples = [
        ("Steel - Polished", {"Base Metal": "Steel", "Finish": "Polished", "Wear Level": "None", "Scratches": False}),
        ("Aluminum - Brushed", {"Base Metal": "Aluminum", "Finish": "Brushed"}),
        ("Bronze - Cast", {"Base Metal": "Bronze", "Finish": "Cast", "Dust": True, "Dust Amount": 0.55}),
        ("Copper - Stonewashed", {"Base Metal": "Copper", "Finish": "Stonewashed", "Wear Level": "Moderate"}),
        ("Steel - Machined + Oil", {"Base Metal": "Steel", "Finish": "Machined", "Oil": True, "Oil Amount": 0.85}),
        ("Custom - Dust + Oil", {"Base Metal": "Custom", "Finish": "Custom", "Custom Metal Color": (0.4, 0.44, 0.48, 1),
                                  "Custom Roughness": 0.4, "Custom Relief mm": 0.02, "Dust": True, "Oil": True,
                                  "Wear Level": "Custom", "Custom Wear": 0.6, "Dust Amount": 0.65}),
    ]
    textmat = bpy.data.materials.new("UM Preview Labels")
    textmat.use_nodes = True
    textmat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.75, 0.8, 0.85, 1)
    bodies = []
    for i, (name, settings) in enumerate(samples):
        x, y = (i % 3 - 1) * 0.07, (0.5 - i // 3) * 0.12
        mat = make_material("UM " + name, library, **settings)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0))
        body = bpy.context.object
        body.name, body.dimensions = name, (0.048, 0.044, 0.036)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y - 0.018, 0.001))
        cutter = bpy.context.object
        cutter.dimensions = (0.027, 0.018, 0.017)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.context.view_layer.objects.active = body
        boolean = body.modifiers.new("Recess", "BOOLEAN")
        boolean.operation, boolean.object = "DIFFERENCE", cutter
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        bevel = body.modifiers.new("Machined Corners", "BEVEL")
        bevel.width, bevel.segments = 0.001, 3
        # Boolean evaluation can create an empty slot: replace it explicitly.
        body.data.materials.clear()
        body.data.materials.append(mat)
        for polygon in body.data.polygons:
            polygon.material_index = 0
        bodies.append(body)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.011, location=(x, y, 0.019))
        cap = bpy.context.object
        cap.name = name + " Curved Sample"
        cap.data.materials.append(mat)
        for poly in cap.data.polygons:
            poly.use_smooth = True
        data = bpy.data.curves.new(name + " Label", "FONT")
        data.body, data.align_x, data.size = name, "CENTER", 0.0032
        obj = bpy.data.objects.new(name + " Label", data)
        scene.collection.objects.link(obj)
        obj.location = (x, y - 0.042, -0.017)
        obj.data.materials.append(textmat)
    world = bpy.data.worlds.new("UM Studio")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.12, 0.16, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, location, power, size in [("Key", (-0.13, -0.15, 0.24), 2.4, 0.2),
                                       ("Fill", (0.16, -0.04, 0.15), 1.6, 0.16), ("Rim", (0, 0.2, 0.2), 2.5, 0.18)]:
        data = bpy.data.lights.new(name, "AREA")
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (-obj.location).to_track_quat("-Z", "Y").to_euler()
        data.energy, data.shape, data.size = power, "DISK", size
    camera = bpy.data.objects.new("Gallery Camera", bpy.data.cameras.new("Gallery Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (0.055, -0.3, 0.29)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale, camera.data.clip_start = "ORTHO", 0.30, 0.001
    scene.render.engine = "CYCLES"
    scene.cycles.samples, scene.cycles.use_denoising = 48, True
    scene.render.resolution_x, scene.render.resolution_y = 1500, 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(directory / "unified_metal_preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    bodies[0].select_set(True)
    bpy.context.view_layer.objects.active = bodies[0]
    bpy.data.images[IMAGE_NAME].filepath = "//textures/oil_smear_mask.png"
    bpy.data.texts.load(str(directory / "unified_metal.py"))
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "unified_metal.blend"))
    if render:
        bpy.ops.render.render(write_still=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.preview:
        preview(Path(__file__).resolve().parent, args.render)
    else:
        meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not meshes:
            raise RuntimeError("Select a mesh before running the generator.")
        mat = make_material()
        for obj in meshes:
            if obj.data.materials:
                obj.data.materials[obj.active_material_index] = mat
            else:
                obj.data.materials.append(mat)
    print("Unified Metal v1 created in Blender", bpy.app.version_string)


if __name__ == "__main__":
    main()
