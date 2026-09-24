"""22未完了の中間成果だけを索引化する。実画像を加工せず複製し、raw計算は含めない。"""
import hashlib
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
CAPTURE=ROOT/'Evidence/Frames/4eabc77e66'
DEST=ROOT/'Evidence/Still_0652da0179';DEST.mkdir(exist_ok=True)
report=json.loads((CAPTURE/'capture_report.json').read_text(encoding='utf8'))
assert report['passed'] and report['cleanup']['all_ui_and_owned_node_checks_passed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
media=[]
for view in ('Front','Perspective'):
 for k in (0,180):
  p=CAPTURE/f'22_{view}_{k:03d}.png';dest=DEST/p.name;dest.write_bytes(p.read_bytes());assert sha(p)==sha(dest)
  media.append({'path':str(dest.relative_to(ROOT)).replace('\\','/'),'source_file':p.name,'sha256':sha(p),'sample':k,'absolute_seconds':k/60,'view':view,'pixels':[1280,720]})
public_capture={'source_run':'0652da0179','actual_houdini_cached_geometry':True,'simulation_recomputed':False,
                'wave_propagation_verified':False,'image_processing':False,
                'raw_capture_report_sha256':sha(CAPTURE/'capture_report.json'),
                'capture_source_sha256':report['source_sha256'],'capture_utc':report['utc'],
                'cleanup':report['cleanup'],'media':media}
(DEST/'22_capture_summary.json').write_bytes((json.dumps(public_capture,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','Houdini/Wave22'],cwd=REPO).decode('utf8').splitlines()
files+=['Docs/Progress/Step_22_ja.md','Docs/Progress/README.md','Docs/Progress/Verification_Status_ja.md','README.md']
entries=[]
for relative in sorted(set(files)):
 p=REPO/relative
 if p.name=='22_provenance.json' or not p.is_file():continue
 entries.append({'path':relative,'bytes':p.stat().st_size,'sha256':sha(p)})
result={'utc':datetime.now(timezone.utc).isoformat(),'step':22,'status_ja':'中間成果。静水の駆動開始判定FAIL、進行波未完成。',
        'repository_head_before_step22':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),
        'working_tree_dirty_at_recording':True,'fluid_wave_verified':False,'unity_wave_output_verified':False,'hmd_verified':False,
        'static_master_token':'0652da0179','wave_video_created':False,'recorded_files':entries}
(ROOT/'Evidence/22_provenance.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'files':len(entries),'total_bytes':sum(r['bytes'] for r in entries),'wave_verified':False}))
