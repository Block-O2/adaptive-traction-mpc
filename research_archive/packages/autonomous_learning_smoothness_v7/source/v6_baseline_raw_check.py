from pathlib import Path
import json,sys,os,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5';sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
ids=['HANDOFF01_BEST','HANDOFF01_BOTHLOW','OPT01_PATTERN011','COMPOSE01_PAIR01','STRICT01_ANT'];rows=[]
for ident in ids:
 r=json.loads((V/'attempts'/f'{ident}_RESULT.json').read_text());m=json.loads((V/r['metrics_path']).read_text());raw=V/'runtime/source/results'/ident
 with np.load(raw/'trace.npz') as z:
  j=z['stage']=='TASK';t=z['time_s'][j];force=z['physical_cuff_force_world_n'][j];mom=z['physical_cuff_moment_world_nm'][j];dt=np.diff(t);jf=float(np.linalg.norm(force[:-1],axis=1)@dt);jm=float(np.linalg.norm(mom[:-1],axis=1)@dt)
 nt=[];v=[];w=[];vi=m['quality']['qvel_indices']
 for n in array_items(raw/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  if t[0]-1e-9<=n['time_s']<=t[-1]+1e-9:
   nt.append(n['time_s']);v.append(np.asarray(n['qvel_evaluation_only'])[vi]);w.append(n.get('cuff_wrench_world_evaluation_only'))
 nt=np.array(nt);v=np.array(v);acc=np.gradient(v,nt,axis=0,edge_order=2);jerk=np.gradient(acc,nt,axis=0,edge_order=2);jr=np.rad2deg(np.sqrt(np.mean(jerk**2,axis=0)));expected=np.array(m['motion']['raw']['full']['jerk_deg_s3']['rms']);assert max(abs(jr-expected))<1e-7;assert abs(jf-r['JF'])<1e-7 and abs(jm-r['JM'])<1e-7
 wr=None
 if w[0] is not None:
  w=np.asarray(w);wr=float(np.sqrt(np.mean((np.gradient(np.linalg.norm(w[:,:3],axis=1),nt,edge_order=2))**2)))
 old_wrench=V/'analysis/native_wrench'/f'{ident}.json'
 if old_wrench.exists() and wr is not None:
  expected_wrench=json.loads(old_wrench.read_text())['force']['norm_rate']['rms'];assert abs(wr-expected_wrench)<1e-8,'V5_WRENCH_METRIC_DEFINITION_MISMATCH'
 rows.append(dict(id=ident,original_qualified=r['qualified'],JF=jf,JM=jm,jerk_RMS_deg_s3=jr.tolist(),force_norm_rate_RMS_N_s=wr,JF_error=jf-r['JF'],JM_error=jm-r['JM'],jerk_max_abs_error=float(max(abs(jr-expected))),native_samples=len(nt)))
 print('BASELINE_RAW',ident,flush=True)
(P/'audit/BASELINE_RAW_RECOMPUTE.json').write_text(json.dumps({'status':'PASS','rows':rows,'new_physical_attempts':0,'source':'actual trace and native qvel/cached wrench; no filtered replacement'},indent=2)+'\n')
