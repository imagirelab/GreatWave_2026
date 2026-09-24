"""実Houdini出力をUnityへ複製し、参照だけを可逆gzip圧縮する。"""
import gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
target=REPO/'Unity/Assets/GreatWave/Art/Playback18';target.mkdir(parents=True,exist_ok=True)
abc=ROOT/'Exports/fluid17.abc';reference=ROOT/'Exports/reference.bytes'
(target/'fluid17.abc').write_bytes(abc.read_bytes())
(target/'reference.bytes').write_bytes(gzip.compress(reference.read_bytes(),compresslevel=9,mtime=0))
assert gzip.decompress((target/'reference.bytes').read_bytes())==reference.read_bytes()
result={'method_ja':'ABCは同一bytes。参照は可逆gzip圧縮だけ。','files':[{'path':str(p.relative_to(REPO)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (abc,reference,target/'fluid17.abc',target/'reference.bytes')]}
(ROOT/'Evidence/18_alembic_integration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
