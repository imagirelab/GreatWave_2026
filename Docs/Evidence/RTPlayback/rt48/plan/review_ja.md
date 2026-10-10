# RT48 計画の独立のレビュー（受け取った文のまま）

- 受け取った日時：2026-10-11 03 時台（計画を凍結する前）。対象は [plan_ja.md](plan_ja.md) の 02:50 の版、[plan_numbers.json](plan_numbers.json)、[../record_ja.md](../record_ja.md)、`Tools/GWWaveGen/rt48/p_inspect.py`。
- 下は、進行役が受け取ったレビューの文を、訳さず、直さずに写したもの（英語）。項目の名前（summary・files・findings・open_issues）は受け取った形のまま。
- 受け取った文は、open_issues の 5 つ目の途中（「and setting PSVR2 to 9」）で切れていた。切れた先は受け取っていない。
- どれを採り、どれを採らなかったかと理由は、[plan_ja.md](plan_ja.md) の §7 に書いた。

---

## summary

I reviewed plan_ja.md, record_ja.md, plan_numbers.json and p_inspect.py, checking them against Q44–Q49, survey §6.1/6.2, the FLIP42 report (§4, §5, appendix B), Step 32, and g_run.py/g_chain2.py. I ran nothing and changed nothing. The plan can go ahead after six changes:
1. Check the fine particle surface inside the lip region. Today it is never compared with the solver's surface there.
2. Make the rule for stopping interpolation topological, and add a self-intersection check.
3. Fix the lip-readability estimate. The lip reach points toward the boat, so it does not show as 80 px. Also stop basing the boat position on the second jet, which does not reproduce between runs.
4. Make 8.9 ms (Step 32's acceptance value) the VR frame-time pass instead of 11.1 ms.
5. State on screen and in the report that this is playback, and that the wave after contact (and the lip's resolution) is unsettled.
6. Follow Q49. It was committed 8 minutes before the plan and the plan never mentions it.

## files

- G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/plan/plan_ja.md
- G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/plan/plan_numbers.json
- G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48/record_ja.md
- G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/rt48/p_inspect.py
- G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/g_run.py
- G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/g_chain2.py
- G:/Unity/GreatWave_2026_Fresh/Docs/Workflow/Production_Workflow_ja.md
- G:/Unity/GreatWave_2026_Fresh/Docs/Research/RealtimeBigWave_Survey_ja.md
- G:/Unity/GreatWave_2026_Fresh/Docs/Progress/FLIP_Plunging_ja.md
- G:/Unity/GreatWave_2026_Fresh/Docs/Progress/Step_32_ja.md

## findings

## Verdict

The plan can go ahead after the changes in items 1–6 below. These parts are sound:
- **Data path, apart from the fine surface.** Records go through a bit-identical re-run (C1), marching squares, uniform arc-length resampling to 8,192 points (C3 ≤ 0.02 m) and a vertex-shader sweep. Nothing in it smooths or reshapes the curve.
- **Vertical datum.** Subtracting 0.117 m moves the whole curve rigidly, so it does not change the shape.
- **Fades.** The fades at the x ends are needed and are reported.
- **Waiting on R4d.** The plan waits for R4d's chain process to end plus 120 s with no hython, which closes the gap the current g_chain2 leaves between launches.
- **Option-2 split.** `ISectionSource` covers what the goal asks for, and nothing more.
- **Rules.** No git, downloads or deletions; RT48 folders only; checks C1–C8 fixed before running.
- **Wording.** Tags are used and none of the forbidden words appear (grep found none).

## Changes needed before running

### 1. The fine surface is a new reconstruction, and nothing checks it where the lip is

Zhu & Bridson with R = 0.5 m and radius r̄ is not the solver's surface. It can make the lip thicker or thinner (by the r̄ offset and the averaging shrink), and it can join the lip to the front face earlier than the solver did.

C2 leaves out the crest ±20 m, which is exactly where this happens:
- Lip thickness is not checked at all.
- Lip reach only triggers "tell the user" if it is off by more than 1.0 m.
- Thickness is the quantity the user and supervisor care about ("唇が薄い", Q45/Q49). A surfacing choice must not change it unnoticed.

Add these checks in the crest window, fixed before the run:
- **Same water region.** The fine water region lies within the solver's water region grown by one solver cell (0.5 m), and the other way round.
- **Same first contact.** The fine surface first encloses air at R3's 3745 (156.0 s) ±1 frame.
- **Lip size.** Thickness within ±0.5 m of 1.06 m and reach within ±0.5 m of 3.65 m. If either fails, fall back to the coarse source.

Also:
- Keep the coarse solver-surface source as a switch in the player, and show it side by side in one video. Then anyone can see the lip was not invented.
- Call it 「粒子から作った細かい面（Zhu & Bridson, 0.125 m）」 in the report, not 「計算の面」.
- Gap: the band limit |φ₀.₅| ≤ 2 m only exists for x 321.5–863 m, because that is all `sec` covers. Playback runs over 100–925 m, so the band outside `sec` is undefined. Use `hf` there, or compute the field everywhere.

### 2. Interpolation can invent shapes in three places the plan does not cover

**a. The stop rule is not topological.** The plan stops interpolating at an enclosed air loop of at least 0.25 m². But any enclosed air loop, or any pinch-off at the lip tip, breaks the arc-length correspondence. Make the rule "the number of loops or pieces of the main curve in the crest ±30 m window changes".

**b. Which interval is last is unclear.** The plan must say that K−1→K is not blended either. The last interpolated interval is [K−2, K−1].

**c. Self-intersection is not checked.** Add a check that no interpolated curve, sampled at 90 Hz steps of α, crosses itself before contact. A blended lip passing through the front face would be an invented contact. C4's curve-to-curve distance does not catch a crossing.

**C4 details:**
- Compute p99 inside the crest window. Over the whole 825 m curve, about 8,000 flat-sea points dilute it.
- Expect failures near contact. The lip tip moves about 0.75 m per frame (`overhang_x` 525.0 → 526.5 → 528.0 m over 3740–3744, 2 frames apart), on a tip of about 0.5 m radius. At the 1/12 s test step that is about 1.5 m, which is outside the regime where error scales with the step squared.
- So "1/4 of the error at playback" is only true if the measured k+2/k+3 ratio shows it. Otherwise the report should say the error at 1/24 s is not measured.
- Consider using the crest and tip landmarks from the start rather than only as a fallback.

### 3. The boat position and camera do not make the lip readable as the plan claims

**The 80 px figure is wrong.** The lip reach (3.65 m) points along +x, straight toward the boat. Seen from the bow it is foreshortened along the line of sight. It is not 4.4° or about 80 px.

From the front, the curl hangs in front of the face (tip about 5–7 m high, below the crest). It is not outlined against the sky. With neutral shading and no shadows, it may hardly show at all. The 1.06 m thickness (about 1.3°, about 23 px) is closer to right.

**The seat rule depends on an event that does not reproduce.** The rule is "overturned water reaches the hull 1.0 s after the second jet". FLIP42 §5 shows the second jet varies between runs: 7.1 m in R3, 4.1 m in R5', 9.1 m in R3m, and none in R2. So the seat is set by an unsettled event.

**Suggested fixes:**
- Base the rule on first contact, which is settled. "Hull reached at least 1 s after first contact" gives about 556 m (hull reached at 157.125 s). From there the crest at contact is about 33.5 m away, about 12° up; at 574 m it is 8°【計算, eye 1.2 m】.
- Before fixing the seat, render coarse-source stills from 556 m and 574 m, plus a view turned 60–80° to look along the crest. That is where the curl shape becomes visible in perspective.
- Offer these as presets for the user. Q49 records the user's own "low wall, thin lip" reading. D7 places the art-piece seat under the lip.
- Optional: take heave from the lowest surface joined to the water below the hull, instead of the topmost one. The clip could then run until water actually lands on the hull. Steep-face pitch would need the user's comfort judgement.

**Comfort after contact.** After contact the boat, and so the VR camera, steps at 24 Hz. Pitch changes up to 12.9°/s, which is about 0.5° jumps. Interpolate the boat's heave and pitch numbers over time. That does not change the wave shape.

### 4. The VR frame-time target is too loose

11.1 ms is the whole 90 Hz frame, with nothing left for the SteamVR compositor or the PSVR2 adapter. Step 32's acceptance was GPU p95 ≤ 8.9 ms.
- Make 8.9 ms the pass, and record 11.1 ms.
- Use Step 32's stereo stand-in (2064×2208 per eye, 96°, IPD 64 mm) next to 2000×2040 and 1.4×, so the results can be compared.
- PSVR2 on PC can run at 120 Hz (8.3 ms per frame). The headset instructions should say to set 90 Hz.
- About 130,000 triangles will very likely pass. The real VR risks are judder, comfort and the compositor.
- Run C7 after the user videos so it does not hold them up (Q29, "show results early").
- For the temporary `enableFrameTimingStats` change: copy ProjectSettings first and restore it in `finally`, as Step 32 did.

### 5. On-screen and report honesty

The captions say the wave is the same along its length. They also need to say:
- 「オフラインで計算した結果の再生で、毎フレーム計算していない」. Survey §6.2 question 1 is still open with the supervisor.
- After contact, the shape is one run's outcome and is not settled. The second jet is 4.1–9.1 m between runs, R3m differs from R3 by 2.0 m, and across the 2 m plate the surface already differs by up to 1.87 m at 158.3 s. So the extruded mid-plate slice is one slice of a flow that was no longer the same across the plate.
- Before contact, the lip's resolution is not judged (R4 not run; R2 vs R3 C3/C4 failed).
- In VR, the "24 コマ/秒・補間なし" notice must at least appear on the end panel.
- The coarse first look needs the label 「粗い元・補間は未確認」.

### 6. Q49 is missing

Q49 was committed at 02:42; the plan was written at 02:50.
- The RT48 report should follow Q49's order: the methods surveyed, the method chosen, the effect achieved, what falls short of the original print, why, and what next. It goes to the supervisor through the user.
- Q49 also says nothing toward option 2 until the supervisor replies. `ISectionSource` is fine, but nothing beyond it.

## Recommended, not blocking

- **Beyond the goal: velocity export.** Particle velocities are kept for white water and option 2. That is about +5 GB (about a third of the 16 GB). Make it optional or drop it.
- **Beyond the goal: Unity side view.** The side cut-away with a filled section and air holes is extra work. A 2-D render in Python from the same baked data is cheaper and shows the same thing.
- **Ends along the crest.** Instead of fading heights at |Z| 700–1,000 m, extend the sweep past the fog distance (about ±10–20 km), so nothing is reshaped along the crest.
  - With only 9 columns 250 m apart, the planned cosine fade becomes roughly a straight ramp across one quad.
  - Normals in the fade would need a z term.
  - Detached water pieces need the same end treatment.
- **r_run/r_chain copies.** The plan names only the output folder and the wait as changes. `runs.jsonl` follows the output root, but `TMP` (`FLIP42/tmp_houdini`) is hard-coded in g_chain2.py and must also move to RT48.
- **C5.** Put the vertex decode in one shared `.hlsl` file that both the shader and the compute check use; otherwise the check re-implements the shader rather than testing it. The 0.0001 m limit is tight against float32 at |X| up to 474 m (spacing about 3e-5 m).
- **Frame choice after contact.** "Nearest frame" shows a frame up to half a frame early. Holding the previous frame would not; or state which is used.
- **C1.** Say which R3 record set is compared. `sec_c2845_*` and `sec_c3319_*` overlap; they should be identical.

## open_issues

- Seat position: 574 m (current rule) vs about 556 m (first contact + 1 s) vs a seat near or under the lip (D7). This needs coarse stills, including a view turned to look along the crest, and the user's choice.
- Whether heave should follow the lowest water surface under the hull instead of the topmost one, which would let the clip run until water lands on the boat. This is a comfort and pitch trade-off for the user.
- Lip-region checks on the fine surface (same water region within 0.5 m, first contact ±1 frame, thickness and reach ±0.5 m) must be added to C2 and written in record_ja.md before the re-run.
- Q49 report structure and where the report goes (Unity/Build/RT48/report vs Docs/Progress) need the user's decision.
- Pass value for C7: 8.9 ms (Step 32 acceptance) vs 11.1 ms; and setting PSVR2 to 9

（受け取った文はここで切れていた。）
