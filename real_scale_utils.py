"""Resize preview studios to real dimensions, preserving lighting and framing."""
import bpy
from mathutils import Matrix


def resize_studio(scene, body, length_m):
    units = scene.unit_settings.scale_length
    factor = length_m / (max(body.dimensions) * units)
    scene.unit_settings.system = 'METRIC'
    if abs(factor - 1) < 0.00001:
        return
    for obj in scene.objects:
        obj.location *= factor
        if obj.type == 'MESH':
            obj.data = obj.data.copy()
            # Bake object scale so Object coordinates reflect scene dimensions.
            obj.data.transform(Matrix.Diagonal((*obj.scale, 1)))
            obj.scale = (1, 1, 1)
            obj.data.transform(Matrix.Scale(factor, 4))
            for modifier in obj.modifiers:
                if modifier.type == 'BEVEL':
                    modifier.width *= factor
        elif obj.type == 'LIGHT':
            obj.data.energy *= factor * factor
            obj.data.size *= factor
        elif obj.type == 'CAMERA':
            obj.data.ortho_scale *= factor
            obj.data.clip_start = min(obj.data.clip_start, 0.001 / units)
    bpy.context.view_layer.update()
