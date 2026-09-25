"""実PFS読戻し画像を原bytesで整理し、時刻字幕付き動画と出典を保存する。Houdini不使用。"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CANDIDATE=Path(__file__).resolve().parents[1]
WAVE=CANDIDATE.parents[1]
FFMPEG=Path('G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe')
FFPROBE=FFMPEG.with_name('ffprobe.exe')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def write(p,d):p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def ass_time(seconds):
    centis=round(seconds*100);return f'{centis//360000}:{centis//6000%60:02d}:{centis//100%60:02d}.{centis%100:02d}'

def main(token,preflight,video):
    run=WAVE/'Runs'/token;dest=CANDIDATE/'Evidence'/('Result_'+token)/'Media';dest.mkdir(exist_ok=True)
    records=[];reports=[]
    for kind,cap in [('preflight',preflight),('video',video)]:
        folder=run/'Capture'/cap;p=folder/'22_capture_report.json';d=load(p)
        assert d['passed'] and not d['transport_completion_uncertain']
        assert d['cleanup']['all_ui_and_owned_node_checks_passed'] and all(d['cleanup']['extra_checks'].values())
        assert len(d['frames'])==(7 if kind=='preflight' else 97)
        assert d['source_sha256']==sha(CANDIDATE/'Postprocess/capture_start04.py')
        for f in d['frames']:
            src=folder/f['image_file'];assert sha(src)==f['image_sha256'] and src.stat().st_size==f['image_bytes']
            assert f['P_and_indices_equal_direct_BGEO'] and f['visible_exact_owned_geometry']
            assert not any(f['flipbook_flags'].values()) and f['global_frame_fixed']==1 and f['fps_unchanged']==24
            assert sha(run/'Cache'/f['cache_file'])==f['cache_sha256']
            if kind=='preflight':(dest/src.name).write_bytes(src.read_bytes())
        # 原reportは成功した撮影のフィールドのみで個人パスを含まない。
        (dest/('22_capture_'+kind+'.json')).write_bytes(p.read_bytes())
        reports.append({'kind':kind,'capture_token':cap,'report_sha256':sha(p),'frame_count':len(d['frames'])})
        records.append(d)
    d=records[1];assert [f['sample']for f in d['frames']]==list(range(360,554,2))
    local=run/'Capture'/video/'Encoding';local.mkdir(exist_ok=True)
    for j,f in enumerate(d['frames']):(local/f'frame_{j:04d}.png').write_bytes((run/'Capture'/video/f['image_file']).read_bytes())
    lines=['[Script Info]','ScriptType: v4.00+','PlayResX: 1280','PlayResY: 720','[V4+ Styles]',
           'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
           'Style: Default,Meiryo,23,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,28,20,25,1',
           '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for j,f in enumerate(d['frames']):
        text='22修正04 実Houdini PFS表示面｜6m短槽・固定正面\\N絶対DOP時刻 %.4f s / k%d｜元キャッシュ読戻し\\N小幅の始動診断：非砕波・無反射・理論精度は未認定'%(f['simulation_seconds'],f['sample'])
        lines.append(f'Dialogue: 0,{ass_time(j/30)},{ass_time((j+1)/30)},Default,,0,0,0,,{text}')
    subtitle='\n'.join(lines)+'\n';(local/'captions.ass').write_bytes(subtitle.encode('utf8'));(dest/'22_startup_captions.ass').write_bytes(subtitle.encode('utf8'))
    movie=dest/'22_startup_PFS.mp4'
    args=['-y','-framerate','30','-start_number','0','-i','frame_%04d.png','-frames:v','97','-vf','subtitles=captions.ass',
          '-fps_mode','passthrough','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(movie)]
    encoded=subprocess.run([str(FFMPEG),*args],cwd=local,capture_output=True,text=True,encoding='utf8',errors='replace');assert encoded.returncode==0,encoded.stderr
    probe=json.loads(subprocess.check_output([str(FFPROBE),'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(movie)]))
    stream=probe['streams'][0];assert (stream['width'],stream['height'],stream['r_frame_rate'],int(stream['nb_read_frames']))==(1280,720,'30/1',97)
    assert abs(float(stream['duration'])-97/30)<1e-5
    decoded=subprocess.run([str(FFMPEG),'-v','error','-i',str(movie),'-f','null','-'],capture_output=True,text=True);assert decoded.returncode==0 and not decoded.stderr
    # 公開記録のコマンドは相対パスとし、実バイナリのSHA/版を別保存する。
    public_args=args[:-1]+['22_startup_PFS.mp4']
    manifest={'simulation_run':token,'captures':reports,'video':{'path':movie.name,'sha256':sha(movie),'bytes':movie.stat().st_size,'probe':stream,'full_decode_errors':0},
              'ffmpeg_version':subprocess.check_output([str(FFMPEG),'-version'],text=True).splitlines()[0],'ffmpeg_sha256':sha(FFMPEG),'ffprobe_sha256':sha(FFPROBE),
              'command_arguments':public_args,'subtitle_sha256':sha(dest/'22_startup_captions.ass'),'font_sha256':sha(Path('C:/Windows/Fonts/meiryo.ttc')),
              'source_sha256':sha(Path(__file__)),'raw_video_frames':d['frames'],
              'meaning_ja':'97枚はk360..552、物理t6..9.2。30fps再生時間3.233333秒の末区間は最後の標本を保持。PFS終端k554/t9.233333は別静止画、solver終端t9.25のPFSはない。字幕だけ追加し、形状・時刻補間・空間拡大なし。'}
    write(dest/'22_media_manifest.json',manifest)
    print(json.dumps({'media':str(dest),'video_frames':97,'full_decode_errors':0},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--preflight',required=True);p.add_argument('--video',required=True);a=p.parse_args();main(a.run,a.preflight,a.video)
