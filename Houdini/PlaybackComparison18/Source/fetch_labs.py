"""公式Labsの固定コミットから、VATと必要な小型HDAだけを取得する。"""
import concurrent.futures,hashlib,json,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='791ecfd07735bb8229fb679f08c000b8489b7a6c'
BASE='https://raw.githubusercontent.com/sideeffects/SideFXLabs/'+COMMIT+'/'
ASSETS=['vertex_animation_textures.3.1.hda','coord_swizzle_quaternion.hda','coord_swizzle_vector.hda','vertical_point_index.hda']
HOTL=r'G:\SteamLibrary\steamapps\common\Houdini Indie\bin\hotl.exe'
tree=json.load(urllib.request.urlopen('https://api.github.com/repos/sideeffects/SideFXLabs/git/trees/'+COMMIT+'?recursive=1'))['tree']
files=[f['path'] for f in tree if f['type']=='blob' and (any(f['path'].startswith('otls/'+a+'/') for a in ASSETS) or f['path']=='LICENSE.md')]
assert len(files)>26
dest=ROOT/'ThirdParty/SideFXLabs';dest.mkdir(parents=True,exist_ok=True)
def fetch(path):
 p=dest/path;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(urllib.request.urlopen(BASE+path).read())
 return {'path':path,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: records=list(pool.map(fetch,files))
packed=[]
for asset in ASSETS:
 source=dest/'otls'/asset;target=dest/asset
 assert source.is_dir(),asset
 subprocess.run([HOTL,'-l',str(source),str(target)],check=True)
 packed.append({'path':str(target.relative_to(ROOT)).replace('\\','/'),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
report={'repository':'https://github.com/sideeffects/SideFXLabs','commit':COMMIT,'files':records,'packed_hdas':packed,'note_ja':'公式VCS展開形式を同梱hotlでpack。Houdiniへの登録は別処理で一時的に行う。'}
(ROOT/'Evidence/18_labs_download.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'files':len(records),'bytes':sum(f['bytes'] for f in records),'packed':packed},ensure_ascii=False))
