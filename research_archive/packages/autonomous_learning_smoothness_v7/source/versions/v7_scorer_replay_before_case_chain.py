"""Cache-bypassing original scorer plus independently rebuilt native motion."""
from pathlib import Path
import os,sys,time,json,gzip,copy,collections
import numpy as np
from acl2_shared import P,R,put,read,sha,utc,records
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc,analyze_matched as am
sys.path.insert(0,str(R/'source/stages/stage5_personalized_motion_learning/scripts/high_rom_v1'))
import evaluate_execution_mode as original_mode

class ArchivePath(type(Path())):
 def read_text(self,*args,**kwargs):
  if self.name=='runtime_artifacts.json' and not self.exists() and Path(str(self)+'.gz').exists():
   with gzip.open(str(self)+'.gz','rt',encoding='utf-8') as f:return f.read()
  return super().read_text(*args,**kwargs)

def rebuild(ident,cached):
 path=R/'source/results'/ident
 with gzip.open(path/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 native=raw['wall_physics']['native_states_evaluation_only'];su=json.loads((path/'summary.json').read_text())
 with np.load(path/'trace.npz') as z:
  task=z['stage']=='TASK';tt=z['time_s'][task];truth=z['evaluation_only_human_state_rad_rad_s'][task];ref=z['reference_q_rad'][task];F=z['physical_cuff_force_world_n'][task];M=z['physical_cuff_moment_world_nm'][task]
 t=np.asarray([r['time_s'] for r in native]);use=(t>=tt[0]-1e-9)&(t<=tt[-1]+1e-9);t=t[use];qi=np.asarray(cached['quality']['qpos_indices']);vi=np.asarray(cached['quality']['qvel_indices']);q=np.asarray([r['qpos_evaluation_only'] for r in native])[use][:,qi];v=np.asarray([r['qvel_evaluation_only'] for r in native])[use][:,vi];del raw,native
 a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2)
 def stats(y):return dict(max_abs=np.max(abs(y),axis=0),p95_abs=np.quantile(abs(y),.95,axis=0),rms=np.sqrt(np.mean(y*y,axis=0)))
 full={k:stats(np.degrees(y)) for k,y in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]};phase=np.full(len(t),'OUTBOUND',dtype='<U10');trans={x['to']:x['time_s'] for x in su['task']['phase_transitions']}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  if ph in trans:phase[t>=trans[ph]-1e-9]=ph
 boundaries={};shapes={}
 for ph in ['OUTBOUND','HOLD','RETURN']:
  idx=np.flatnonzero(phase==ph);u=(t[idx]-t[idx[0]])/(t[idx[-1]]-t[idx[0]]);boundaries[ph]=dict(start_deg=np.degrees(q[idx[0]]),end_deg=np.degrees(q[idx[-1]]));shapes[ph]=np.degrees(np.column_stack([np.interp(np.linspace(0,1,201),u,q[idx,d]) for d in range(2)]))
 m=copy.deepcopy(cached);m['motion']['raw']['full']=sc.clean(full);m['dose']=sc.clean(dict(duration_s=t[-1]-t[0],excursion_deg=np.degrees(np.ptp(q,axis=0)),cumulative_travel_deg=np.degrees(np.sum(abs(np.diff(q,axis=0)),axis=0)),endpoint_deg=np.degrees(q[-1]),phase_boundaries=boundaries,phase_shapes=shapes));m['J_F_N_s']=float(np.linalg.norm(F[:-1],axis=1)@np.diff(tt));m['moment_integral_Nm_s']=float(np.linalg.norm(M[:-1],axis=1)@np.diff(tt));m['force_peak_N']=float(np.max(np.linalg.norm(F,axis=1)));m['moment_peak_Nm']=float(np.max(np.linalg.norm(M,axis=1)));m['tracking_RMS_deg']=np.degrees(np.sqrt(np.mean((truth[:,:2]-ref)**2,axis=0))).tolist();m['phase_durations']=dict(OUTBOUND=trans['HOLD']-tt[0],HOLD=trans['RETURN']-trans['HOLD'],RETURN=trans['COMPLETE']-trans['RETURN']);return m

def replay(ident,group):
 path=R/'source/results'/ident;dp=R/'output'/(ident+'_DATA.json');mp=R/'reports'/(ident+'_MEASURED.json')
 if not (dp.exists() and (path/'summary.json').exists() and (path/'trace.npz').exists()):return dict(id=ident,status='PARTIAL_NOT_RANKED',formal_force_rank_allowed=False)
 data=json.loads(dp.read_text());old=data['metric']['physical_audit']['unchanged_evaluator'];case_path=P/json.loads((P/'experiments'/(group+'.json')).read_text()).get('case_path','runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json');case_data=json.loads(case_path.read_text());case=dict(case_key=case_data['case_key'],physical_variant=case_data['cell']['family'],candidate=case_data['coordination_candidate'],path=str(case_path.relative_to(R/'source')),sha256=sha(case_path));scoring=read('runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring']
 fresh=sc.clean(original_mode.evaluate(ArchivePath(path),case,scoring,goal_deg=case_data['task']['goal_deg'],start_deg=case_data['task']['start_deg']));errors=[]
 for key in ['physical_task_result','scientific_validity','overall_result_for_mode','raw_scorer_v2']:
  if fresh[key]!=old[key]:errors.append('ORIGINAL_SCORER_VERDICT_OR_FIELDS:'+key)
 result=dict(id=ident,group=group,utc=utc(),original_mode_result=fresh['overall_result_for_mode'],original_physical_result=fresh['physical_task_result']['status'],original_scientific_result=fresh['scientific_validity']['status'],original_result_exact_reproduced=not errors,motion_replay=None,qualified_replay=False)
 if mp.exists():
  cached=json.loads(mp.read_text());m=rebuild(ident,cached);Bident=group+'_B';bm=R/'reports'/(Bident+'_MEASURED.json');baseline=P/'audit/scorer_baselines'/(Bident+'.json')
  if ident==Bident:b=m;put('audit/scorer_baselines/'+Bident+'.json',b)
  elif baseline.exists():b=json.loads(baseline.read_text())
  elif bm.exists():b=rebuild(Bident,json.loads(bm.read_text()));put('audit/scorer_baselines/'+Bident+'.json',b)
  else:b=None
  if b is not None:
   comp=am.compare(m,b);expected=am.compare(cached,json.loads(bm.read_text()));matched=sc.r2.matched_eligible(m['phase_durations']);qualified=bool(comp['acceptance_pass'] and matched and fresh['overall_result_for_mode']=='PASS')
   if comp['acceptance_pass']!=expected['acceptance_pass'] or sorted(comp['failed_requirements'])!=sorted(expected['failed_requirements']):errors.append('ORIGINAL_MOTION_SCORER_VERDICT')
   rfile=P/'attempts'/(ident+'_RESULT.json')
   if rfile.exists() and json.loads(rfile.read_text())['qualified']!=qualified:errors.append('FINAL_QUALIFICATION_VERDICT')
   result.update(motion_replay=dict(acceptance_pass=comp['acceptance_pass'],failed_requirements=comp['failed_requirements'],original_timing_R2_matched=matched),qualified_replay=qualified,independent_JF=m['J_F_N_s'],independent_JM=m['moment_integral_Nm_s'],independent_native_dose=m['dose'],independent_native_motion=m['motion']['raw']['full'])
 result.update(status='SCORER_REPLAY_PASS' if not errors else 'SCORER_REPLAY_MISMATCH',errors=errors,source_sha256=sha(__file__),unchanged_scorer_sources={str(f.relative_to(P)):sha(f) for f in [Path(original_mode.__file__),Path(original_mode.score.__code__.co_filename),R/'code/explore_common.py',R/'code/analyze_matched.py']},input_sha256={str(f.relative_to(P)):sha(f) for f in [path/'trace.npz',path/'summary.json',path/'runtime_artifacts.json.gz',dp]});return result

def summary():
 files=sorted((P/'audit/scorer_replay').glob('*.json')) if (P/'audit/scorer_replay').exists() else [];rr=[json.loads(f.read_text()) for f in files];out=dict(utc=utc(),status='PASS' if all(r['status'] in ['SCORER_REPLAY_PASS','PARTIAL_NOT_RANKED'] for r in rr) else 'REVIEW_REQUIRED',audited=len(rr),physical_START=sum(r['event']=='START' for r in records()),status_counts=dict(collections.Counter(r['status'] for r in rr)),mismatches=[r for r in rr if r['status'] not in ['SCORER_REPLAY_PASS','PARTIAL_NOT_RANKED']],method='Original evaluate_execution_mode.evaluate invoked directly, bypassing cached SAC audit; gzip text read-only adapter preserves original scorer code/thresholds. Native v/a/jerk and dose independently rebuilt, then original mode-aware motion comparison rerun. Same agent, separate replay code path.');put('audit/UNCHANGED_SCORER_REPLAY.json',out);return out

def finish_missing():
 for r in records():
  if r['event']!='START':continue
  f=P/'audit/scorer_replay'/(r['id']+'.json')
  if f.exists():continue
  try:row=replay(r['id'],r.get('group','INTERFACE'))
  except Exception as e:row=dict(id=r['id'],status='SCORER_REPLAY_ERROR',error=str(e))
  put('audit/scorer_replay/'+r['id']+'.json',row)
 return summary()

def main():
 A=read('ACTIVATION.json');deadline=A['hard_stop_unix']-600;put('owned/SCORER_SERVICE_START.json',dict(utc=utc(),pid=os.getpid(),deadline_unix=deadline,source_sha256=sha(__file__)))
 try:
  for _ in range(20000):
   if time.time()>deadline or (P/'CLOSURE_START.json').exists() or (P/'END.json').exists():break
   ev=records();ended={r['id'] for r in ev if r['event']=='END'};count=0
   for r in ev:
    if r['event']!='START' or r['id'] not in ended or (P/'audit/scorer_replay'/(r['id']+'.json')).exists():continue
    dp=R/'output'/(r['id']+'_DATA.json');mp=R/'reports'/(r['id']+'_MEASURED.json')
    if dp.exists() and json.loads(dp.read_text()).get('metric',{}).get('task_valid') and not mp.exists():continue
    try:row=replay(r['id'],r.get('group','INTERFACE'))
    except Exception as e:row=dict(id=r['id'],status='SCORER_REPLAY_ERROR',error=str(e))
    put('audit/scorer_replay/'+r['id']+'.json',row);count+=1
   s=summary()
   if count:print('ORIGINAL_SCORER_REPLAY',count,'TOTAL',s['audited'],s['status'],flush=True)
   time.sleep(6)
 finally:put('owned/SCORER_SERVICE_END.json',dict(utc=utc(),pid=os.getpid(),status='STOP'))
if __name__=='__main__':main()
