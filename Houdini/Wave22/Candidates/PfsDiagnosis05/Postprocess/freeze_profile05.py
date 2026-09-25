"""05公開候補の原bytes・解析・文書を相対pathのSHA一覧に固定する。"""
import hashlib
import json
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
ROOT=CANDIDATE.parents[3]
DEST=CANDIDATE/'Evidence/22_revision05_provenance.json'
def main():
    docs=[ROOT/p for p in ('README.md','Houdini/Wave22/README_ja.md','Docs/Progress/README.md','Docs/Progress/Step_22_ja.md','Docs/Progress/Verification_Status_ja.md')]
    files=docs+[p for p in CANDIDATE.rglob('*')if p.is_file()and p!=DEST and'__pycache__'not in p.parts]
    records=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(files)]
    assert len(records)==len({r['path']for r in records})
    data={'revision':'22修正05','baseline_commit':'d3be3eb205f6e3ff91c215806bb85df84976cac6','records':records,
          'total_bytes':sum(r['bytes']for r in records),'profile_original_manifest':'Houdini/Wave22/Candidates/PfsDiagnosis05/Evidence/Result_22e7801642/22_profile05_original_manifest.json',
          'solver_executed_in_revision05':False,'step22_complete':False,
          'meaning_ja':'自己ファイルを除く05公開候補。原gzip展開SHA、実行source、画像/CSV/統計、文書を結ぶ。BGEO本体やローカルRunsは含めない。'}
    DEST.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'files':len(records),'bytes':data['total_bytes'],'provenance_sha256':hashlib.sha256(DEST.read_bytes()).hexdigest()}))

if __name__=='__main__':main()
