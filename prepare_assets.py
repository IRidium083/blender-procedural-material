"""Mark current library materials as assets; run with Blender -b -P this file.

Re-run after regenerating material scenes. Does not modify user preferences.
"""
from pathlib import Path
import uuid
import bpy

ROOT = Path(__file__).resolve().parent
CATALOGS = {name: str(uuid.uuid5(uuid.NAMESPACE_URL, 'material-library/' + name))
            for name in ('Metals', 'Painted Surfaces', 'Plastics and Rubber')}
SCENES = [
    ('worn_painted_metal', 'Painted Surfaces', 'recessed_metal_cycles.png'),
    ('machined_metal', 'Metals', 'machined_metal_preview.png'),
    ('phosphated_gun_steel', 'Metals', 'phosphated_gun_steel_preview.png'),
    ('textured_grip', 'Plastics and Rubber', 'textured_grip_preview.png'),
]


def materials():
    return [m for m in bpy.data.materials if m.node_tree
            and any(n.type == 'GROUP' for n in m.node_tree.nodes)]


def main():
    catalog = ROOT / 'blender_assets.cats.txt'
    existing = catalog.read_text(encoding='utf-8') if catalog.exists() else '# Material library catalogs\nVERSION 1\n'
    for name, catalog_id in CATALOGS.items():
        if catalog_id not in existing:
            existing += f'{catalog_id}:{name}:{name}\n'
    catalog.write_text(existing, encoding='utf-8')
    total = 0
    for folder, category, thumbnail in SCENES:
        path = ROOT / folder / (folder + '.blend')
        bpy.ops.wm.open_mainfile(filepath=str(path))
        selected = materials()
        assert selected, f'No material node groups in {path}'
        for mat in selected:
            mat.asset_mark()
            mat.use_fake_user = True
            mat.asset_data.catalog_id = CATALOGS[category]
            mat.asset_data.description = f'{mat.name}. Editable material group; see {folder}/README.md for controls and scale guidance.'
            for tag in (category, 'Material', 'Blender 5.2'):
                mat.asset_data.tags.new(tag, skip_if_exists=True)
            with bpy.context.temp_override(id=mat):
                bpy.ops.ed.lib_id_load_custom_preview(filepath=str(ROOT / folder / thumbnail))
        # Pack external image dependencies before publishing the asset file.
        for image in bpy.data.images:
            if image.source == 'FILE' and image.users and not image.packed_file:
                image.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        # Verify persisted metadata, thumbnails and packed texture dependencies.
        bpy.ops.wm.open_mainfile(filepath=str(path))
        for mat in materials():
            assert mat.asset_data and mat.asset_data.catalog_id == CATALOGS[category]
            assert mat.preview and mat.preview.image_size[0] > 0
            total += 1
            print(f'ASSET PASS: {mat.name} / {category}')
        for image in bpy.data.images:
            if image.source == 'FILE' and image.users:
                assert image.packed_file, image.name
    print(f'PASS: {total} material assets across {len(SCENES)} scene files')


if __name__ == '__main__':
    main()
