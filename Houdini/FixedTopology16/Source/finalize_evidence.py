"""実キャプチャを数値フレーム順に整理し、30fps・2秒の動画と検証記録を作る。"""
import hashlib,json,math,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOKEN='449e318fa476'
FFMPEG=Path(r'G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe')
FFPROBE=FFMPEG.with_name('ffprobe.exe')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):
 p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stderr
 return p.stdout
frames=sorted((ROOT/'Evidence/Frames').glob(TOKEN+'_*.png'),key=lambda p:float(p.stem[len(TOKEN)+1:]))
assert len(frames)==60 and len({p.name for p in frames})==60
outdir=ROOT/'Evidence/PreviewFrames';outdir.mkdir(exist_ok=True)
records=[]
for k,p in enumerate(frames):
 actual=float(p.stem[len(TOKEN)+1:]);expected=1+k*24/30
 assert abs(actual-expected)<0.0002,(actual,expected)
 dst=outdir/('frame_%03d.png'%k);shutil.copyfile(p,dst)
 records.append({'index':k,'time_seconds':k/30,'houdini_frame_from_filename':actual,'sha256':sha(p),'bytes':p.stat().st_size})
for k,label in ((0,'start'),(15,'half_second'),(30,'one_second')):
 shutil.copyfile(outdir/('frame_%03d.png'%k),ROOT/('Evidence/fixed_topology_16_'+label+'.png'))
video=ROOT/'Evidence/fixed_topology_16_houdini_preview.mp4'
run([FFMPEG,'-y','-loglevel','error','-framerate','30','-start_number','0','-i',outdir/'frame_%03d.png','-frames:v','60','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',video])
probe=json.loads(run([FFPROBE,'-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',video]))
v=probe['streams'][0];assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_read_frames']))==(1280,720,'30/1',60)
assert abs(float(v['duration'])-2)<1e-6
run([FFMPEG,'-v','error','-i',video,'-f','null','-'])
report={'source_capture_report':'preview_449e318fa476.json','classification':'Actual Houdini viewport of kinematic analytic sample; construction grid is a viewport overlay. Not a FLIP result or final art.','rejected_capture':'../Evidence/run_379f9b5c42eb.json: inward normals and close framing rejected; source winding corrected in run_67145e6aeacb.json and fitted camera preview_449e318fa476.json adopted','frame_count':60,'fps':30,'duration_seconds':2,'frames':records,'distinct_frame_hashes':len({r['sha256'] for r in records}),'all_frames_different':len({r['sha256'] for r in records})==60,'video_probe':probe,'full_video_decode_passed':True,'video_sha256':sha(video),'video_bytes':video.stat().st_size,'ffmpeg_version':run([FFMPEG,'-version']).splitlines()[0]}
(ROOT/'Evidence/preview_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('frame_count','duration_seconds','distinct_frame_hashes','video_probe','full_video_decode_passed','video_bytes')},ensure_ascii=False))

