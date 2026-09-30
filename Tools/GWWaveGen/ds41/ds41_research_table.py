# -*- coding: utf-8 -*-
"""設計41 調査：押送船の寸法表 JSON を書く（資料の値と絵からの推定を分ける）。"""
import json, hashlib, datetime

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/41/research/oshiokuri_dimensions.json"
PAINT = r"G:/Unity/GreatWave_2026_Fresh/Docs/References/Met_JP1847_DP130155.jpg"
SHAKU = 10.0 / 33.0  # 曲尺 1尺（m）。1891 年の度量衡法の定義。1813 年の史料の尺を曲尺と仮定

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

L_src = 38.5 * SHAKU
B_src = 8.2 * SHAKU
D_src = 3.0 * SHAKU

placed = {  # 番号27・27修正01 の記録（Step_27_ja.md、seat_v1.json）
    "boat_fg": {"tip_to_tip_m": 8.45, "depth_plane_m": 29.48, "role_ja": "手前の船（75）"},
    "boat_mid": {"tip_to_tip_m": 11.328, "depth_plane_m": 45.8367, "role_ja": "右の船（159）。座席 v1 の船"},
    "boat_left": {"tip_to_tip_m": 9.98, "depth_plane_m": 50.30, "role_ja": "左奥の船（157）"},
}
for k, v in placed.items():
    s = v["tip_to_tip_m"] / L_src
    v["model_scale_if_projection_kept"] = round(s, 4)
    v["deviation_from_source_length_percent"] = round((s - 1) * 100, 2)
    kk = L_src / v["tip_to_tip_m"]
    v["alt_k_to_make_full_size"] = round(kk, 4)
    v["alt_depth_after_k_m"] = round(v["depth_plane_m"] * kk, 2)

S = {
    "S1": {"org_ja": "ウィキペディア日本語版「押送船」（二次資料。出典として 石井謙治『和船 II』法政大学出版局 1995、pp.164–167 を挙げる）",
            "url": "https://ja.wikipedia.org/wiki/%E6%8A%BC%E9%80%81%E8%88%B9", "kind": "二次（百科。一次の典拠は書籍）", "status": "読んだ"},
    "S2": {"org_ja": "コトバンク「押送船」：ブリタニカ国際大百科事典 小項目事典、精選版 日本国語大辞典",
            "url": "https://kotobank.jp/word/%E6%8A%BC%E9%80%81%E8%88%B9-40241", "kind": "辞典", "status": "読んだ"},
    "S3": {"org_ja": "国立国会図書館 レファレンス協同データベース（回答：鎌倉市中央図書館）「押送船」",
            "url": "https://crd.ndl.go.jp/reference/entry/index.php?page=ref_view&id=1000185601", "kind": "公的機関（図書館）", "status": "読んだ（寸法の記述なし。典拠の書誌7点）"},
    "S4": {"org_ja": "太田記念美術館 公式 note「北斎の波の細部に迫って鑑賞してみた」（2021-05-14）",
            "url": "https://otakinen-museum.note.jp/n/n04c44025350c", "kind": "美術館", "status": "読んだ"},
    "S5": {"org_ja": "すみだ北斎美術館 収蔵品「冨嶽三十六景 神奈川沖浪裏」",
            "url": "https://hokusai-museum.jp/modules/Collection/collections/view/47?lang=ja", "kind": "美術館", "status": "読んだ（寸法なし）"},
    "S6": {"org_ja": "東京富士美術館 収蔵品「冨嶽三十六景 神奈川沖浪裏」",
            "url": "https://www.fujibi.or.jp/collection/artwork/03628/", "kind": "美術館", "status": "読んだ（寸法なし）"},
    "S7": {"org_ja": "文化遺産オンライン（文化庁）「冨嶽三十六景・神奈川沖浪裏」東京国立博物館",
            "url": "https://online.bunka.go.jp/heritages/detail/568372", "kind": "公的機関・国立博物館", "status": "読んだ（寸法なし）"},
    "S8": {"org_ja": "ウィキペディア英語版 The Great Wave off Kanagawa（Cartwright & Nakamura 2009, Notes Rec. R. Soc. 63, pp.121・123 を引く）",
            "url": "https://en.wikipedia.org/wiki/The_Great_Wave_off_Kanagawa", "kind": "二次（百科。一次は論文）", "status": "読んだ。論文の頁 https://royalsocietypublishing.org/doi/10.1098/rsnr.2007.0039 は 403 で未読"},
    "S9": {"org_ja": "船の科学館 もの知りシート No.32「弁才船の構造と各部名称」（日本財団図書館 電子図書館）",
            "url": "https://nippon.zaidan.info/seikabutsu/2002/00033/contents/032.htm", "kind": "博物館（和船一般の構造用語）", "status": "読んだ"},
    "S10": {"org_ja": "コトバンク「櫓」：改訂新版 世界大百科事典、日本大百科全書(ニッポニカ)",
             "url": "https://kotobank.jp/word/%E6%AB%93-143570", "kind": "辞典（和船一般の櫓）", "status": "読んだ"},
    "S11": {"org_ja": "文化遺産オンライン「押送舟図」館山市立博物館",
             "url": "https://online.bunka.go.jp/heritages/detail/437829", "kind": "公的機関・市立博物館", "status": "読んだ（作品の書誌のみ。船の寸法の記述なし）"},
}

HOLD = [
    {"what_ja": "郵政博物館 研究紀要 第10号（2019）の論文（押送船を扱う）", "url": "https://www.postalmuseum.jp/publication/research/research_10_16.pdf",
     "reason_ja": "PDF ファイルの取得はダウンロードに当たるため読まない（利用者の許可が要る）。保留"},
    {"what_ja": "千葉市立郷土博物館の X の投稿（押送船の解説。検索結果の抜粋では『船首の四角い枠は生簀』）", "url": "https://x.com/chibashikyodo/status/1223440762370576386",
     "reason_ja": "HTTP 402 で本文を読めない。検索結果の抜粋だけで、値としては使わない（絵の読みの裏づけ候補として記録）"},
    {"what_ja": "ボストン美術館 北斎『押送波濤通船』（Express Delivery Boats Rowing through Waves）", "url": "https://collections.mfa.org/objects/234341",
     "reason_ja": "HTTP 403。押送船を正面から描いた別の北斎作品で、船の形の参照候補。未読"},
    {"what_ja": "メトロポリタン美術館 45434（本作の所蔵館の解説）", "url": "https://www.metmuseum.org/art/collection/search/45434", "reason_ja": "HTTP 429。未読"},
    {"what_ja": "大英博物館 A_1906-1220-0-533 と公式ブログ", "url": "https://www.britishmuseum.org/collection/object/A_1906-1220-0-533", "reason_ja": "HTTP 403。未読"},
    {"what_ja": "横浜市歴史博物館 企画展「津々浦々百千舟－江戸時代横浜の海運」（2017）", "url": "https://www.rekihaku.city.yokohama.jp/koudou/see/kikakuten/2016/20170128_wasentosuiun/", "reason_ja": "接続拒否。未読"},
    {"what_ja": "石井謙治『和船 II』（法政大学出版局 1995）pp.164–167、『神奈川県史 各論編5』p.331、『神奈川県民俗調査報告3』p.61 ほか（S3 の典拠）", "url": None, "reason_ja": "書籍。ウェブで本文を読めないので、値は S1 の引用として扱う"},
]

src_values = [
    {"item": "length_oa", "label_ja": "全長", "value_m": round(L_src, 4), "original": "38尺5寸", "src": ["S1"],
     "note_ja": "1813 年の史料（S1 は 石井謙治『和船 II』pp.164–167 を典拠に挙げる）。1尺＝10/33 m（曲尺と仮定）で 11.667 m。S1 の表記は 11.7 m"},
    {"item": "length_oa_alt_britannica", "label_ja": "長さ（別の資料）", "value_m": 12.0, "original": "長さ約 12m", "src": ["S2"], "note_ja": "ブリタニカ国際大百科事典"},
    {"item": "length_oa_alt_ota", "label_ja": "全長（別の資料）", "value_m": 10.0, "original": "全長は10メートルほど", "src": ["S4"], "note_ja": "太田記念美術館。概数"},
    {"item": "length_oa_range_cn2009", "label_ja": "長さの範囲（別の資料）", "value_m": [12.0, 15.0], "original": "generally between 12 and 15 metres", "src": ["S8"],
     "note_ja": "Cartwright & Nakamura 2009 p.123（S8 経由）。同論文は船から波高 10〜12 m を推定（北斎が縦を 30% 縮めた前提）"},
    {"item": "beam_max", "label_ja": "幅", "value_m": round(B_src, 4), "original": "8尺2寸", "src": ["S1", "S2"], "note_ja": "S1 は 2.5 m、ブリタニカも 2.5 m。どこで測った幅か（舷の外か梁の外か）は資料に書かれていない"},
    {"item": "depth_midship", "label_ja": "深さ", "value_m": round(D_src, 4), "original": "3尺", "src": ["S1"], "note_ja": "S1 は 0.9 m。測り方（航の上面から上棚の上縁まで、など）は資料に書かれていない"},
    {"item": "ro_count", "label_ja": "櫓の数", "value": 7, "original": "7丁の艪／櫓7丁／七挺の櫓", "src": ["S1", "S2"]},
    {"item": "mast_count", "label_ja": "帆柱", "value": 3, "original": "3本の着脱式のマスト", "src": ["S1"], "note_ja": "着脱式。本作では帆柱は立っていない（絵の読み P7）"},
    {"item": "sail", "label_ja": "帆", "value": "6反", "original": "帆6反／六反の帆", "src": ["S2"]},
    {"item": "construction", "label_ja": "構造", "value": "二階造り・尖鋭な船型・船首が高い", "original": "尖鋭な船型をもった二階造り（精選版 日本国語大辞典）", "src": ["S2", "S9"],
     "note_ja": "二階造り＝航（かわら。平らな船底材）に根棚と上棚を付け、中棚のない棚板造り（和船一般の用語は S9）。ブリタニカは船首が高く鋭い船型とする"},
    {"item": "crew_cn2009", "label_ja": "乗員（本作の読み）", "value": {"rowers": 8, "others_at_front": 2}, "original": "eight rowers ... two more relief crew members", "src": ["S8"],
     "note_ja": "Cartwright & Nakamura 2009 p.121（S8 経由）。本作の3隻で30人、見えるのは22人"},
    {"item": "crew_ota", "label_ja": "乗員（見える人数）", "value": {"front_boat": 10, "rear_boat": 11, "third_boat": 2}, "src": ["S4"], "note_ja": "太田記念美術館の数え。どの船をどう呼ぶかは S4 の記述どおり"},
    {"item": "use", "label_ja": "用途", "value_ja": "房総・伊豆・安房など江戸周辺から江戸（日本橋の市場など）へ鮮魚を急送する帆走・漕走併用の小型快速船", "src": ["S1", "S2", "S3", "S5", "S6", "S7"]},
    {"item": "fleet_1803", "label_ja": "隻数の記録", "value": 64, "original": "1803年（享和3年）に江戸周辺で64隻", "src": ["S1"]},
    {"item": "ro_generic", "label_ja": "櫓の寸法（和船一般。押送船の値ではない）", "value_m": {"arm": [1.5, 2.1], "leg": [4.2, 5.5], "width": [0.13, 0.15]},
     "original": "腕が1.5～2.1m，脚が4.2～5.5mで幅は13～15cm", "src": ["S10"], "note_ja": "改訂新版 世界大百科事典。支点は櫓杭（櫓臍）に櫓の入子を差す（日本大百科全書）"},
]

painting = {
    "image": {"path": "Docs/References/Met_JP1847_DP130155.jpg", "sha256": sha(PAINT), "size_px": [3859, 2594],
              "display_map_ja": "表示 1920×1080 は原画の高さを 1080 に合わせた左右の余白付き（s = 1080/2594、x 余白 156.66 px）。番号27 の manual_landmarks.json の両端をこの写像で原画の画素へ戻した"},
    "estimates": [
        {"id": "P1", "label_ja": "配置済みの船の長さ（先端間）", "value_m": {k: v["tip_to_tip_m"] for k, v in placed.items()},
         "basis_ja": "番号27（深度平面を M1 の深さに固定し、原画の両端の射線へ合わせた）と 27修正01（右船を投影中心から 0.7754 倍）。絵そのものの寸法ではなく、置き方の結果"},
        {"id": "P2", "label_ja": "三日月形の反り（両端を結ぶ弦から舷の上縁の最も低い所までの距離 ÷ 弦の長さ）", "value": {"boat_fg": 0.12, "boat_mid": 0.18},
         "basis_ja": "原画の画素で読んだ（手前の船：弦 1610 px、舷の上縁は弦より約 200 px 下。右の船：弦 1389 px、約 244 px 下）。透視と船の傾きを含む見かけの値で、実船の反りではない。誤差 ±20%"},
        {"id": "P3", "label_ja": "舷側の見える高さ ÷ 弦の長さ（手前の船、船体中央）", "value": {"upper_strake_pink": 0.05, "whole_side_incl_light_band": 0.105},
         "basis_ja": "薄紅の上の帯は約 80 px、下の淡い帯を含めて約 170 px（弦 1610 px）。資料の深さ÷全長は 0.078。一本の縫い目（点列）が帯の境に通る"},
        {"id": "P4", "label_ja": "人物の頭の大きさから見た船の長さ", "value_m": [6.2, 7.7],
         "basis_ja": "手前の船の漕ぎ手の頭の幅は約 42 px（弦 1610 px の 0.026）。頭の幅 0.16〜0.20 m とすると 6.2〜7.7 m。資料の 11.7 m より短く、北斎は人物を船に対して約 1.5〜1.9 倍に描いたと読める（乗員の作り込みは仕上げ41）"},
        {"id": "P5", "label_ja": "船首寄りの簀の子状の枠と藁の房", "value": {"from_bow_fraction": [0.12, 0.40]},
         "basis_ja": "手前の船で、船首から弦の約 0.12〜0.40 の区間に、格子の枠と下に垂れる藁の房がある。生簀の蓋か苫かは資料で確かめられない（千葉市立郷土博物館の投稿の抜粋は『船首の四角い枠は生簀』だが未読、保留）"},
        {"id": "P6", "label_ja": "漕ぎ手の位置と姿勢", "value": {"rowers_zone_from_bow_fraction": [0.55, 1.0]},
         "basis_ja": "手前・右の船とも、漕ぎ手は船尾側の約半分にかがみ込んで櫓（または櫂）にしがみつく。立って漕ぐ姿ではない"},
        {"id": "P7", "label_ja": "帆柱・帆", "value": "描かれていない", "basis_ja": "3隻とも帆柱は立っていない（資料の『着脱式』と矛盾しない）"},
        {"id": "P8", "label_ja": "右の船の船尾の梯子状の枠", "value_rel_len": 0.11,
         "basis_ja": "船体の上縁から約 150 px（弦 1389 px の約 0.11、11.3 m の船で約 1.2 m）立つ細い柱と枠。用途は資料で未確認（番号27 は船の長さに含めていない）"},
        {"id": "P9", "label_ja": "船首", "value": "鋭く尖り、高く反り上がる",
         "basis_ja": "3隻とも船首は細く尖って上がる。資料（S2 の『尖鋭』『船首が高く』）と合う"},
    ],
}

adopted = {
    "note_ja": "設計41 のモデルに使う値。資料の値をそのまま採るもの（source）と、資料がないため推定したもの（estimate）を分ける。推定は設計42（静水の釣り合い）と仕上げ41 で見直す",
    "items": [
        {"item": "length_oa_m", "value": round(L_src, 3), "kind": "source", "src": ["S1"]},
        {"item": "beam_max_m", "value": round(B_src, 3), "kind": "source", "src": ["S1", "S2"], "interp_ja": "舷の上縁（上棚の外）の最大幅と読む（推定の読み方）"},
        {"item": "depth_midship_m", "value": round(D_src, 3), "kind": "source", "src": ["S1"], "interp_ja": "船体中央で船底（航の下面）から舷の上縁までと読む（推定の読み方）"},
        {"item": "construction", "value": "航＋根棚＋上棚（二階造り）、船梁で補強", "kind": "source", "src": ["S2", "S9"]},
        {"item": "ro_count", "value": 7, "kind": "source", "src": ["S1", "S2"]},
        {"item": "ro_length_m", "value": {"arm": 1.5, "leg": 4.2, "width": 0.13, "total": 5.7}, "kind": "estimate",
         "basis_ja": "和船一般の櫓の範囲（S10）の下限。押送船の櫓の寸法の資料はない"},
        {"item": "ro_layout", "value": "左舷4・右舷3を船尾側の約6割に交互", "kind": "estimate", "basis_ja": "資料なし。絵の漕ぎ手の位置（P6）と櫓7丁から"},
        {"item": "masts", "value": "立てない（モデルに入れないか、寝かせた形で置く）", "kind": "estimate", "basis_ja": "P7。資料は3本の着脱式"},
        {"item": "bow_sheer_rise_m", "value": 0.9, "kind": "estimate", "basis_ja": "資料なし。船首が高い（S2）ことと、絵の強い反り（P2）の間の控えめな値（全長の約 0.08）。絵に合わせた強い反りは仕上げ41"},
        {"item": "stern_sheer_rise_m", "value": 0.5, "kind": "estimate", "basis_ja": "資料なし。船尾は戸立（S9 の和船一般）とし、船首より低く反らせる"},
        {"item": "floor_above_bottom_m", "value": 0.2, "kind": "estimate", "basis_ja": "資料なし。航と床船梁の厚み程度。舷の上縁は床から約 0.71 m"},
        {"item": "mass_total_t", "value": 2.0, "range": [1.6, 3.1], "kind": "estimate",
         "basis_ja": "資料なし。船体（杉の板 厚さ約 3.5 cm、密度 400 kg/m³ 程度、梁・航・櫓・帆柱を含め約 1.0〜1.5 t）＋乗員10人（約 0.6 t）＋荷（0〜1 t）"},
        {"item": "draft_m", "value": 0.20, "range": [0.16, 0.30], "kind": "estimate",
         "basis_ja": "資料なし。排水容積 = 質量 / 1025 kg/m³ を、水線長 10.5 m・水線幅 2.1 m・方形係数 0.45 で割った値（2.0 t で 0.20 m、1.6〜3.1 t で 0.16〜0.30 m）。設計42 で浮力点から出し直す。今の blockout は 0.38 m"},
        {"item": "freeboard_midship_m", "value": round(D_src - 0.20, 3), "kind": "estimate", "basis_ja": "深さ 0.909 − 喫水 0.20"},
    ],
}

seat = {
    "seat_v1_eye_above_deck_m": 1.2,
    "seat_v1_json": "Tools/GWContext/seat_v1.json（変えない。計画 R11）",
    "estimate_eye_above_gunwale_m": round(1.2 - (D_src - 0.2), 3),
    "estimate_eye_above_gunwale_scaled_m": round(1.2 - (D_src - 0.2) * placed["boat_mid"]["model_scale_if_projection_kept"], 3),
    "note_ja": "床が船底から 0.2 m（推定）なら、舷の上縁は床から 0.71 m。座位の目 1.2 m（腰掛け）は舷の上縁より約 0.49 m 上（右船を 0.971 倍で置けば約 0.51 m）。床に直に座る姿勢（目 約 0.8 m）なら舷の上縁とほぼ同じ高さで、外が見えにくい。実際の甲板の高さは設計41 のモデルで測り直して記録する",
}

doc = {
    "schema": "GreatWave.Design41.oshiokuri_research/1",
    "number": "設計41",
    "part": "research",
    "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "unit_note_ja": "1尺 = 10/33 m（0.30303 m、曲尺と仮定）。1813 年の史料の尺の種類は資料に書かれていない",
    "policy_ja": "ウェブのページを読んだだけで、ファイルはダウンロードしていない。資料の値（source_values）と絵からの推定（painting_estimates）と、モデルに使う採用値（adopted_for_model、source／estimate を明記）を分ける",
    "sources": S,
    "held_sources": HOLD,
    "source_values": src_values,
    "painting_estimates": painting,
    "adopted_for_model": adopted,
    "current_blockouts": {
        "base_blockout_ja": "M1 の blockout（3隻共通）：先端間 10.0 m、船体中央の深さ 0.96 m、喫水 = 0.35 × 0.96 × 縮尺（Step_27_ja.md、Step_27_修正01_ja.md）",
        "boats": placed,
        "recommendation_ja": "投影固定のまま（両端の射線と深度は変えない）、全長 11.667 m のモデルを各船の先端間へ縮尺して置く。座席の右船は 0.971 倍で資料の全長から −2.9%（5% の内）。手前 0.724 倍・左奥 0.855 倍は資料より小さいままで、差は記録して仕上げ41 で判断する（実寸にするには手前を深さ 40.7 m、左奥を 58.8 m へ動かす必要があり、原画視点の重なりが変わる）",
    },
    "seat_v1_vs_gunwale": seat,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
print(OUT, sha(OUT))
print(json.dumps(placed, ensure_ascii=True))
print(seat["estimate_eye_above_gunwale_m"], seat["estimate_eye_above_gunwale_scaled_m"])
