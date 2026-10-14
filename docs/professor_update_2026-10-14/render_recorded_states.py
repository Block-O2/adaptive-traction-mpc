"""Evaluation-only rendering of recorded physical states; no simulation advance."""
import os,sys,json,time,hashlib
from pathlib import Path
os.environ['MUJOCO_GL']='egl'
R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1')
for stage in ['stage1','stage2_linkage','stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:
 for base in [R,P/'source']:
  sys.path.insert(0,str(base/'stages'/stage/'src'))
import numpy as np,mujoco,imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant
D=R/'docs/professor_update_2026-10-14'; A=D/'assets'; A.mkdir(parents=True,exist_ok=True)
case=json.loads((P/'CURRENT_MODEL_AND_TASK.json').read_text())['case']
human,geometry,_,_=hidden_plant(case)
plant=Stage5CR12SpringDamperPlant(human=human,geometry=geometry)
plant.model.vis.global_.offwidth=800;plant.model.vis.global_.offheight=480
renderer=mujoco.Renderer(plant.model,height=480,width=800)
cam=mujoco.MjvCamera(); cam.type=mujoco.mjtCamera.mjCAMERA_FREE
cam.lookat[:]=[0.30,0.0,0.52];cam.distance=2.85;cam.azimuth=-90;cam.elevation=-14
opt=mujoco.MjvOption();opt.geomgroup[:]=1
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
names=[('baseline','development_repair2_B0_original'),('coordination_18d','development_repair2_quality_NATIVE_SCALAR_18_063')]
traces=[np.load(P/'source/results'/n/'trace.npz') for _,n in names]
indices=[np.flatnonzero(t['stage']=='TASK') for t in traces]
if '--probe' in sys.argv:
 for az in [-90,-65,65,90,180,0]:
  for k in [indices[0][0],indices[0][1800]]:
   t=traces[0];plant.data.qpos[plant.human_qpos_indices]=t['evaluation_only_human_state_rad_rad_s'][k,:2];plant.data.qpos[plant.robot_qpos_indices]=t['cr12_q_rad'][k]
   mujoco.mj_forward(plant.model,plant.data);cam.azimuth=az;renderer.update_scene(plant.data,camera=cam,scene_option=opt)
   Image.fromarray(renderer.render()).save('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/camera_'+str(az)+'_'+str(k)+'.png')
 renderer.close();sys.exit()
fps=20; elapsed=np.arange(0,19.030+1e-7,1/fps); elapsed=np.r_[elapsed,19.030]
writers=[]
for filename,size in [('baseline',(800,480)),('coordination_18d',(800,480)),('comparison',(1600,480))]:
 w=imageio_ffmpeg.write_frames(str(A/(filename+'.mp4')),size,fps=fps,codec='libx264',pix_fmt_out='yuv420p',output_params=['-crf','25','-preset','fast','-movflags','+faststart'])
 w.send(None);writers.append(w)
errors=[];start=time.monotonic()
for frame,dt in enumerate(elapsed):
 views=[]
 for j,(label,n) in enumerate(names):
  t=traces[j]; ids=indices[j]; target=t['time_s'][ids[0]]+dt
  k=int(np.clip(np.searchsorted(t['time_s'],target),ids[0],ids[-1]))
  if k>ids[0] and abs(t['time_s'][k-1]-target)<abs(t['time_s'][k]-target):k-=1
  plant.data.qpos[plant.human_qpos_indices]=t['evaluation_only_human_state_rad_rad_s'][k,:2]
  plant.data.qvel[plant.human_dof_indices]=t['evaluation_only_human_state_rad_rad_s'][k,2:]
  plant.data.qpos[plant.robot_qpos_indices]=t['cr12_q_rad'][k]
  plant.data.qvel[plant.robot_dof_indices]=t['cr12_dq_rad_s'][k]
  plant.data.time=float(t['time_s'][k]);mujoco.mj_forward(plant.model,plant.data)
  errors.append(float(np.linalg.norm(plant.data.site_xpos[plant.attachment_site_id]-t['physical_cuff_position_world_m'][k])))
  renderer.update_scene(plant.data,camera=cam,scene_option=opt)
  im=Image.fromarray(renderer.render()); draw=ImageDraw.Draw(im)
  draw.rectangle((0,0,800,55),fill='#142032')
  draw.text((16,7),('Baseline B' if j==0 else '18D Development Best')+' | '+str(t['task_phase'][k])+' | task t='+f'{dt:.2f}s',font=font,fill='white')
  draw.text((16,31),'Recorded physical state replay | MuJoCo | LEVEL 1 | 1x',font=font,fill='#b7d9df')
  ar=np.asarray(im);writers[j].send(ar);views.append(ar)
  if frame in [0,180,220,380]:im.save(A/(label+f'_frame_{frame:03d}.png'))
 writers[2].send(np.concatenate(views,axis=1))
 if frame%80==0:print('RENDER',frame,len(elapsed),round(time.monotonic()-start,1),flush=True)
for w in writers:w.close()
renderer.close()
assert max(errors)<1e-7,('MODEL_STATE_MISMATCH',max(errors))
manifest={'method':'MuJoCo full mesh rendering of recorded physical robot and Human boundary states; mj_forward only, no new physics run, no state interpolation','fps':fps,'frames':len(elapsed),'duration_s':len(elapsed)/fps,'task_duration_s':19.03,'max_reconstructed_cuff_error_m':max(errors),'camera':{'lookat':list(cam.lookat),'distance':cam.distance,'azimuth':cam.azimuth,'elevation':cam.elevation},'source_cases':[],'videos':[]}
for label,n in names:
 f=P/'source/results'/n/'trace.npz';manifest['source_cases'].append({'label':label,'case':n,'trace_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'trace_path':str(f)})
for f in A.glob('*.mp4'):manifest['videos'].append({'file':f.name,'bytes':f.stat().st_size})
(D/'VIDEO_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print('COMPLETE',json.dumps(manifest),flush=True)
