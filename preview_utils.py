"""Shared studio lighting and camera setup for material previews."""
import bpy
from mathutils import Vector

def setup_studio(scene, target):
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
