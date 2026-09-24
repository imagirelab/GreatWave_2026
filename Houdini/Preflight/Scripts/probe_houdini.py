"""新規シーンだけで Houdini の実ライセンス、cook、保存を確認する。"""
print('M1_HOUDINI_SCRIPT_STARTED', flush=True)
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = {'schema_version': 1, 'status': 'NOT_STARTED', 'hmd_validation': 'NOT_RUN'}
try:
    import hou
    report['houdini_version'] = hou.applicationVersionString()
    report['license_category'] = str(hou.licenseCategory())
    report['ui_available'] = hou.isUIAvailable()
    hou.hipFile.clear(suppress_save_prompt=True)
    container = hou.node('/obj').createNode('geo', 'm1_license_geometry_probe', run_init_scripts=False)
    box = container.createNode('box', 'unit_box')
    geometry = box.geometry()
    report['points'] = len(geometry.points())
    report['primitives'] = len(geometry.prims())
    report['bounds_size'] = list(geometry.boundingBox().sizevec())
    geometry.saveToFile(str(ROOT / 'Exports' / 'probe_unit_box.bgeo.sc'))
    sop_types = hou.sopNodeTypeCategory().nodeTypes()
    rop_types = hou.ropNodeTypeCategory().nodeTypes()
    report['available_sop_candidates'] = sorted(name for name in sop_types if
        any(tag in name.lower() for tag in ('flip', 'particlefluid', 'vertex_animation', 'labs::')))
    report['available_rop_candidates'] = sorted(name for name in rop_types if
        any(tag in name.lower() for tag in ('alembic', 'fbx', 'vertex_animation')))
    report['sidefx_labs_env'] = hou.getenv('SIDEFXLABS')
    report['status'] = 'COOK_AND_BGEO_SAVE_PASSED'
except Exception as exc:
    report['status'] = 'FAILED'
    report['exception_type'] = type(exc).__name__
    report['error'] = str(exc)
finally:
    path = ROOT / 'Evidence' / 'houdini_geometry_probe.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('M1_HOUDINI_GEOMETRY_PROBE=' + json.dumps(report, ensure_ascii=False))
