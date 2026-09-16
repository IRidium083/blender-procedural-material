"""GPU-first Cycles setup for all material preview generators.
Run without --factory-startup and with --save-preferences to persist device choice.
"""
from pathlib import Path
import sys
import bpy


def configure_cycles(scene):
    scene.render.engine = 'CYCLES'
    preferences = bpy.context.preferences.addons['cycles'].preferences
    chosen = None
    for backend in ('OPTIX','CUDA','HIP','ONEAPI','METAL'):
        try:
            preferences.compute_device_type = backend
            devices = preferences.get_devices_for_type(backend)
        except (TypeError,ValueError,RuntimeError):
            continue
        gpu = [device for device in devices if device.type == backend]
        if gpu:
            for device in preferences.devices:
                device.use = device.type == backend
            scene.cycles.device = 'GPU'
            chosen = backend
            print('Cycles GPU:',backend,', '.join(device.name for device in gpu))
            break
    if chosen is None:
        preferences.compute_device_type = 'NONE'
        scene.cycles.device = 'CPU'
        print('Cycles: no supported GPU found; using CPU.')
    # Keep generator Text Editor execution portable in saved preview files.
    path = Path(globals().get('__file__',''))
    if path.is_file():
        text = bpy.data.texts.get('render_utils.py') or bpy.data.texts.new('render_utils.py')
        text.clear()
        text.write(path.read_text(encoding='utf-8'))
        text.filepath = str(path.resolve())
    return chosen


if __name__ == '__main__':
    configure_cycles(bpy.context.scene)
    if '--save-preferences' in sys.argv:
        bpy.ops.wm.save_userpref()
