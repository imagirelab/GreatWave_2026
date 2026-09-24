"""正式VATの実ファイルをUnityへ複製し、公式materialの符号化パラメーターを保持する。"""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];source=ROOT/'Exports/VAT_Final';target=REPO/'Unity/Assets/GreatWave/Art/Playback18/VAT';target.mkdir(parents=True,exist_ok=True)
files=['geo/fluid17_mesh.fbx','tex/fluid17_lookup.exr','tex/fluid17_pos.exr','tex/fluid17_rot.exr'];records=[]
for name in files:
 p=source/name;assert p.stat().st_size>1000,p;q=target/p.name;q.write_bytes(p.read_bytes());records.append({'source':str(p.relative_to(REPO)).replace('\\','/'),'unity':str(q.relative_to(REPO)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
material=(source/'unity/fluid17_mat.mat').read_text(encoding='utf8')
fields={key:float(re.search(r'- '+key+r': ([^\r\n]+)',material).group(1)) for key in ['_boundMinX','_boundMinY','_boundMinZ','_boundMaxX','_boundMaxY','_boundMaxZ','_frameCount','_houdiniFPS']}
data={'frameCount':int(fields['_frameCount']),'sampleRate':fields['_houdiniFPS'],'encodedMin':dict(zip('xyz',[fields['_boundMin'+x] for x in 'XYZ'])),'encodedMax':dict(zip('xyz',[fields['_boundMax'+x] for x in 'XYZ']))}
assert data['frameCount']==49 and data['sampleRate']==24
(target/'metadata.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
(ROOT/'Evidence/18_vat_integration.json').write_text(json.dumps({'files':records,'encoded_parameters':data,'official_material_sha256':hashlib.sha256((source/'unity/fluid17_mat.mat').read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf8')
print(json.dumps({'bytes':sum(r['bytes'] for r in records),'metadata':data}))
