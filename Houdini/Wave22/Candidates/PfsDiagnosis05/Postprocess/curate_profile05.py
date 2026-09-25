"""実読戻し原bytesを公開候補へ無損失保存する。Houdini/MCPは使用しない。"""
import gzip
import hashlib
import json
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
DEST=CANDIDATE/'Evidence/Result_22e7801642'
BASE=WAVE/'Candidates/WaveStart04/Evidence/Result_22e7801642'
RUNS=['profiles05_77a1b7dda9','profiles05_894837442e']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))

def main():
    DEST.mkdir(parents=True,exist_ok=True);records=[];samples=[];executions=[]
    def preserve(source,relative,kind,compress=False):
        raw=source.read_bytes();target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
        payload=gzip.compress(raw,compresslevel=9,mtime=0)if compress else raw
        if target.exists():assert target.read_bytes()==payload,'既存公開候補の原bytesを変更しない'
        else:target.write_bytes(payload)
        records.append({'path':relative,'kind':kind,'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),
                        'stored_sha256':sha(target),'stored_bytes':len(payload),'gzip':compress})
    for token in RUNS:
        run=WAVE/'Runs'/token;execution=json.loads((run/'execution.json').read_bytes())
        assert execution['all_requested_completed']and execution['passed_for_continuation']and not execution['transport_completion_uncertain']
        executions.append(execution)
        preserve(run/'execution.json',f'Original/{token}_execution.json','execution')
        for event in execution['events']:
            p=run/event['result_file'];assert sha(p)==event['result_sha256']and p.stat().st_size==event['result_bytes']
            preserve(p,'Original/'+p.name+'.gz','profile',True);samples.append(event['sample'])
        for name,h in execution['source_hashes'].items():
            p=run/'Source'/name;assert sha(p)==h
            if token==RUNS[0]:preserve(p,'Executed_Source/'+name,'executed_source')
            else:assert sha(DEST/'Executed_Source'/name)==h
    assert samples==list(range(468,527,2))
    plan=json.loads((DEST/'Executed_Source/profile05_plan.json').read_bytes())
    for relative,h in plan['baseline_files'].items():
        p=BASE/relative;assert sha(p)==h
        preserve(p,'Baseline04/'+relative,'baseline04')
    preserve(CANDIDATE/'Evidence/22_profile05_offline_checks.json','22_profile05_offline_checks.json','offline_checks')
    source_manifest=json.loads((BASE/'22_cache_manifest.json').read_bytes())
    selected=[]
    for r in source_manifest['cache_files']:
        if r['filename']in{f'{kind}_{k:03d}.bgeo.sc'for k in samples for kind in('pilot','mesh')}:
            p=WAVE/'Runs/22e7801642/Cache'/r['filename'];assert sha(p)==r['sha256']and p.stat().st_size==r['bytes'];selected.append(r)
    assert len(selected)==60
    write(DEST/'22_profile05_cache_manifest.json',{'baseline_run':'22e7801642','baseline_manifest_sha256':sha(BASE/'22_cache_manifest.json'),
          'files':selected,'files_rehashed':60,'bytes':sum(r['bytes']for r in selected),'solver_executed':False,
          'meaning_ja':'05が読んだ60個の既存BGEO。物理計算は04で実施済み。本体は本機Runs、公開は原SHAと読戻しJSON。'})
    write(DEST/'22_profile05_original_manifest.json',{'records':records,'profile_count':30,
          'profile_source_bytes':sum(r['source_bytes']for r in records if r['kind']=='profile'),
          'profile_gzip_bytes':sum(r['stored_bytes']for r in records if r['kind']=='profile'),
          'meaning_ja':'mtime=0 gzip展開bytesはHoudiniが書いた原JSONと完全一致。実行記録も元bytesを保持。'})
    print(json.dumps({'profiles':30,'records':len(records),'profile_gzip_bytes':sum(r['stored_bytes']for r in records if r['kind']=='profile'),'houdini_called':False}))

if __name__=='__main__':main()
