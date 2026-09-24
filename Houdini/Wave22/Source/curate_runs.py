"""計算済みの軽量原記録を公開用に複製する。巨大cacheとraw tracebackはローカルに残す。"""
import hashlib
import gzip
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'Evidence/Curated_Runs'
SOURCES=DEST/'Executed_Source'
SOURCES.mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,d):d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(p.read_bytes());assert sha(p)==sha(d)

for token in sys.argv[1:]:
 report_path=ROOT/'Evidence'/('run_'+token+'.json')
 report=json.loads(report_path.read_text(encoding='utf8'))
 assert report.get('cleanup',{}).get('all_ui_and_owned_node_checks_passed') is True
 original=ROOT/'Runs'/token
 dest=DEST/token;dest.mkdir(exist_ok=True)
 manifest={}
 for name in ('22_pilot_conditions.json','22_pilot_samples.json','22_collision_probe.json','22_initialization_schema.json','22_preroll_stability.json','22_bottom_connection.json','22_bottom_connection_execution.json','22_initial_particle_identity.json'):
  p=original/'Evidence'/name
  if p.exists():
   copy(p,dest/name);manifest[name]={'sha256':sha(p),'bytes':p.stat().st_size}
 executed=[]
 for p in sorted((original/'Source').glob('*.py')):
  h=sha(p);assert h==report['source_hashes'][p.name]
  relative='Executed_Source/'+h+'_'+p.name
  if p.read_bytes().endswith(b'\n\n'):
   # 実行当時の余分な終端空行も改変しない。無損失圧縮で元bytesを保管する。
   old=DEST/relative;relative+='.gz';stored=DEST/relative
   stored.write_bytes(gzip.compress(p.read_bytes(),mtime=0));assert gzip.decompress(stored.read_bytes())==p.read_bytes()
   if old.exists():
    assert old.resolve().parent==SOURCES.resolve();old.unlink()
   compression='gzip'
  else:
   stored=DEST/relative;copy(p,stored);compression=None
  executed.append({'name':p.name,'path':relative,'sha256':h,'compression':compression,'stored_sha256':sha(stored)})
 summary={'token':token,'arguments':report.get('arguments'),'utc':report['utc'],
          'execution_success':report.get('success',False),'raw_report_local_relative_path':'Evidence/run_'+token+'.json',
          'raw_report_sha256':sha(report_path),'files':manifest,'executed_source':executed,
          'cleanup':report['cleanup'],'failure_type':report.get('failure',{}).get('type'),
          'cache_location_ja':'ローカル Runs/'+token+'/Cache。公開時系列に各cacheのSHAを保持。',
          'scope_ja':'接続と初期過渡の実測。波・収支・理論精度の合格ではない。'}
 (dest/'execution_summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 print(token)
