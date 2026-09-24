"""19の実アーカイブを同bytesでUnityへ置き、検査参照だけ可逆gzip化する。"""
import gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];dest=REPO/'Unity/Assets/GreatWave/Art/Sampling19';dest.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rows=json.loads((ROOT/'Evidence/19_alembic_exports.json').read_text(encoding='utf8'))['exports'];assert len(rows)==4
copied=[]
for row in rows:
 source=ROOT/row['path'];target=dest/source.name;assert sha(source)==row['sha256'] and source.stat().st_size<100000000
 shutil.copyfile(source,target);assert sha(target)==row['sha256'];copied.append({'path':str(target.relative_to(REPO)).replace('\\','/'),'bytes':target.stat().st_size,'sha256':sha(target)})
source=ROOT/'Exports/reference60.bytes';target=dest/'reference60.bytes';target.write_bytes(gzip.compress(source.read_bytes(),compresslevel=6,mtime=0));assert gzip.decompress(target.read_bytes())==source.read_bytes()
copied.append({'path':str(target.relative_to(REPO)).replace('\\','/'),'bytes':target.stat().st_size,'sha256':sha(target),'decompressed_bytes':source.stat().st_size,'decompressed_sha256':sha(source)})
(ROOT/'Evidence/19_unity_integration.json').write_text(json.dumps({'source_clip':'GreatWave19_FLIP60_01','files':copied},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(copied,indent=2))
