"""実行済みの18書出し記録を要約する。Houdiniへ接続せず、正式ファイルの実bytesを再確認する。"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'Evidence'/name).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
abc=read('18_alembic_export.json');vat=read('18_vat_second.json')
assert digest(ROOT/'Exports/fluid17.abc')==abc['sha256']
for row in vat['files']:
    p=ROOT/row['path'];assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256']
runs=[]
for name,role in [('run_e1439cd31f.json','参照49時刻・Alembicの正式出力'),('run_5eb861068d.json','不採用：VAT範囲の既定式が240まで残り、空画像と欠落警告'),('run_c11631687f.json','修正pass1の実出力完了。ただし旧ブリッジ120秒応答期限を超過'),('run_0fccca8a8f.json','正式pass2。同tokenの完了記録を確認し、実ファイルを統合')]:
    r=read(name)
    runs.append({'historical_run':name,'role_ja':role,'token':r['token'],'source_hashes_at_execution':r['source_hashes'],'failure':r.get('failure'),'cleanup':r.get('cleanup'),'unregister':r.get('unregister'),'wrapper_success':r.get('success')})
    assert r['cleanup']['all_ui_and_owned_node_checks_passed'] and r['unregister']['all_temporary_hdas_unregistered']
summary={'clip_id':'GreatWave17_FLIP_02','input':'17の採用surface_000〜048.bgeo.sc。再計算なし。','sample_count':49,'fps':24,'relative_seconds':[0,2],
 'alembic':abc,'vat':vat,'vat_first_pass_seconds':read('18_vat_first.json')['seconds'],
 'vat_binary_bytes_excluding_material':sum(x['bytes'] for x in vat['files'] if not x['path'].endswith('.mat')),
 'runs':runs,'source_note_ja':'実行時ソースSHAは各runに固定。現在の再現用スクリプトには後の診断/出典修正を含むため同一bytesとは主張しない。',
 'scope_ja':'所有ノードと一時HDA登録だけを生成・削除。HIP保存/読込・全シーン走査・FPS/ライセンス/既存プラグイン変更なし。Undoと変更済みフラグは消去しない。',
 'unity_status_ja':'Unity復号/描画の合否はDocs/Evidence/M1/Playback18の独立した実測で判定する。',
 'passed_export_artifact_hashes':True}
(ROOT/'Evidence/18_export_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('正式ABC/VATの出力ハッシュとUI復元記録を確認しました。')
