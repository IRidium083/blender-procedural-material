"""Update and verify grip/steel saved studios at real scale, then render Cycles."""
from pathlib import Path
import importlib.util
import sys
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_scale_utils import resize_studio

ROOT = Path(__file__).resolve().parent
for folder, body_name, length in [
    ('textured_grip', 'Hard Rubber Grip Sample', 0.2),
    ('phosphated_gun_steel', 'Machined Steel Sample', 0.28),
]:
    directory = ROOT / folder
    path = directory / (folder + '.blend')
    bpy.ops.wm.open_mainfile(filepath=str(path))
    spec = importlib.util.spec_from_file_location(folder, directory / (folder + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene = bpy.context.scene
    resize_studio(scene, bpy.data.objects[body_name], length)
    mats = [module.make_material()]
    if folder == 'textured_grip':
        mats.append(module.make_material(True))
    for mat in mats:
        instance = next(n for n in mat.node_tree.nodes if n.type == 'GROUP')
        assert instance.inputs['Edge Width'].default_value <= 0.0011
        assert instance.inputs['Meters Per Unit'].default_value == scene.unit_settings.scale_length
        group = instance.node_tree
        assert group.nodes['Coordinates in Meters'].inputs['Scale'].is_linked
        for node in group.nodes:
            if node.type in {'BUMP', 'AMBIENT_OCCLUSION'}:
                assert node.inputs['Distance'].is_linked, node.name
        assert not mat.asset_data
    source = directory / (folder + '.py')
    for block in bpy.data.texts:
        if block.name.startswith(folder + '.py'):
            block.clear()
            block.write(source.read_text(encoding='utf-8'))
            block.filepath = str(source)
    assert abs(max(bpy.data.objects[body_name].dimensions) * scene.unit_settings.scale_length - length) < 0.001
    scene.render.engine = 'CYCLES'
    scene.render.filepath = str(directory / (folder + '_preview.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.render.render(write_still=True)
    print(f'PASS: {folder} real-size studio, metric coordinates, converted AO and bump distances')
