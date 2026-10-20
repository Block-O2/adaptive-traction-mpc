from pathlib import Path
import os, sys, json, time, shutil, hashlib, subprocess, collections
sys.dont_write_bytecode=True
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
S=ROOT/'m2_coordination_space_exploration_v1'; OLD=ROOT/'m2_host_generalization_attribution_v1'
WIN=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
T0=1791478620.0 # Conservative 2026-10-09 00:57 Asia/Shanghai, before first request read.
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def git(p):
 def call(*a):
  r=subprocess.run(['git','-C',str(p),*a],capture_output=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'));return {'returncode':r.returncode,'stdout':r.stdout.decode(errors='replace'),'stderr':r.stderr.decode(errors='replace')}
 idx=call('rev-parse','--git-path','index')['stdout'].strip();ip=Path(idx);ip=ip if ip.is_absolute() else p/ip
 return dict(branch=call('branch','--show-current'),head=call('rev-parse','HEAD'),status=call('status','--porcelain=v1','--untracked-files=all'),diff=call('diff','--binary'),staged=call('diff','--cached','--binary'),index_sha256=sha(ip) if ip.is_file() else None)
def main():
 assert not S.exists();S.mkdir()
 for d in ['reports','preservation','queue','logs','output','versions','motion_series']:(S/d).mkdir()
 roots=[Path('/home/hank/coding/adaptive-traction-mpc-learning'),Path('/home/hank/coding/adaptive-traction-mpc-human-closeout-git'),WIN.parent]
 save(S/'preservation/GIT_BEFORE.json',{str(p):git(p) for p in roots})
 prior=json.loads((ROOT/'m2_motion_counterfactual_ranking_v1/PRESERVATION_BEFORE.json').read_text())
 paths={r['path'] for r in prior['files']}
 for pkg in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1','m2_neural_q_motion_v1','m2_motion_counterfactual_ranking_v1']:
  paths.update(str(p) for p in (ROOT/pkg).rglob('*') if p.is_file())
 save(S/'preservation/HISTORY_BEFORE.json',{p:sha(p) for p in sorted(paths)})
 reloc=[]
 for d in ['code','source','deps','native','build','weights','versions']:
  shutil.copytree(OLD/d,S/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('results','__pycache__','.git'))
  for p in (S/d).rglob('*'):
   if p.is_file() and p.suffix in ['.py','.json','.xml','.yaml','.yml','.toml','.sh']:
    txt=p.read_text();new=txt.replace(str(OLD),str(S)).replace('m2_host_generalization_attribution_v1','m2_coordination_space_exploration_v1')
    if new!=txt:
     a=sha(p);p.write_text(new);reloc.append(dict(path=str(p.relative_to(S)),before=a,after=sha(p),change='package path relocation'))
 (S/'source/results').mkdir(exist_ok=True)
 for n in ['HISTORICAL_K3_DESIGN_REFERENCE.json','SHARED_COORDINATION_ACTION_CONTRACT.json','C13_LOCAL_EQUIVALENCE.json','C12_LOCAL_EQUIVALENCE.json']:shutil.copy2(OLD/'output'/n,S/'output'/n)
 shutil.copy2(OLD/'TIMING_BASELINE.json',S/'TIMING_BASELINE.json');shutil.copy2(OLD/'reports/OFFLINE_INTERFACE_GATE.json',S/'reports/OFFLINE_INTERFACE_GATE.json')
 save(S/'preservation/SOURCE_RELOCATION.json',reloc)
 # Table proposals use the existing immutable TASK envelope and certificates.
 p=S/'code/host_adapter.py';txt=p.read_text();needle="COORD=q_first_method.QFirstInterface({**config,'delay_replay':False})"
 assert needle in txt
 txt=txt.replace(needle,"\n if config.get('coordination_table') is not None:\n  from exploration_coordinator import TableCoordinator\n  COORD=TableCoordinator(config)\n else:\n  COORD=q_first_method.QFirstInterface({**config,'delay_replay':False})")
 p.write_text(txt)
 for p in WIN.glob('*.py'):
  if p.name!='bootstrap.py':shutil.copy2(p,S/'code'/p.name)
 shutil.copy2(WIN/'bootstrap.py',S/'bootstrap.py')
 import numpy as np
 H=np.asarray(json.loads((S/'output/HISTORICAL_K3_DESIGN_REFERENCE.json').read_text())['table']).reshape(2,5,3)
 tables=[]
 for scale in [.025,.05,.10,.20,.35,.50]:
  x=np.zeros_like(H);x[1]=H[1]*scale;tables.append((f'return_history_scale_{scale:g}',x))
 for scale in [.05,.20]:tables.append((f'both_history_scale_{scale:g}',H*scale))
 for name,knots in [('flat',[-.05,-.05,-.05]),('early',[-.08,-.03,0]),('late',[0,-.03,-.08]),('tent',[-.025,-.05,-.025])]:
  x=np.zeros_like(H);x[1]=knots;tables.append(('return_'+name,x))
 # 2 baselines + 12 discovery tables, 6 held-seed comparisons, at most 4 reserved.
 configs=[];base=json.loads((OLD/'queue/001_deviation_P1_seed1_B.json').read_text())
 def config(name,method,seed,table=None,split='search'):
  c=dict(base);c.update(id=name,method=method,seed=seed,prefix={},weights=str(S/'weights/frozen_Q_v1'),pair_id='nominal_'+str(seed),pair_condition='nominal',split=split,host_coordinator=True)
  c.pop('durable_config_path',None)
  if table is not None:c['coordination_table']=table.tolist()
  return c
 configs.append(config('001_search_B','M0',2026100901,np.zeros_like(H)))
 configs.append(config('002_search_frozen_M2','M2',2026100901))
 for i,(name,x) in enumerate(tables,3):configs.append(config(f'{i:03d}_{name}','M0',2026100901,x))
 for c in configs:save(S/'queue'/(c['id']+'.json'),c)
 protocol=dict(version=1,registered_unix=time.time(),start_unix=T0,deadline_unix=T0+10800,dispatch_cutoff_unix=T0+9600,wall_cap_s=10800,physics_attempt_cap=24,discovery_attempts=14,validation_reserved=6,other_reserved=4,clock='REALTIME_CHARACTERIZATION; actual original host worker envelope; no formal realtime qualification',fixed_Human='existing exposed nominal high-ROM Human; frozen commissioning semantics; no persistent session',initial_conditions='cold full-task fixed nominal initial conditions per seed; commissioning outcomes measured, not forcibly matched',same_intermediate_state_counterfactual=False,search_ranges=dict(K=3,slots_per_phase=5,normalized_action=[-1,1],delta_bound=.2,knot_fractions=[.1,.4,.7],tables=[dict(id=c['id'],table=c.get('coordination_table'),method=c['method']) for c in configs]),candidate_generation='12 deterministic registered amplitude/phase/PWL-shape tables; no hidden physics rollout or surrogate ranking',selection='After all feasible discovery attempts, eligible iff original physical/causal/trace PASS and primary motion acceptance PASS and J_F at least 0.5% below paired B. Select lowest full-task J_F, tie ID. Must be lower than frozen M2 or have materially lower burden while improving B to qualify as valuable.',validation=dict(seeds=[2026100902,2026100903],order=['B,candidate,M2','M2,candidate,B'],choice_frozen_before_test=True,criterion='both independent-seed pairs meet primary acceptance, J_F improves B by >=0.5%, comparison to M2 reported separately; no reselection'),stop=['physical safety or task-contract failure','causal ownership failure','trace integrity failure','wall or attempt cap','negative candidate results do not trigger threshold changes'],stage_D_gate='Only if C has no valuable executable improvement AND source audit supports a missing native freedom. No forced extension; at most single offline conceptual diagnostic if contract change needed.',training=0,heavy_physics_parallel=False,full_task='original OUTBOUND/HOLD/RETURN/COMPLETE, ROM/goals/dt/scheduler/governor/40ms bridge/100ms expiry/current-state admission/ownership/fallback unchanged',historical_E='Read-only reference, different clock/commissioning cannot be subtracted; not a current matched arm unless separately registered within remaining cap')
 save(S/'EXPERIMENT_PROTOCOL.json',protocol);save(S/'RUN_PLAN.json',dict(start_unix=T0,deadline_unix=T0+10800,dispatch_cutoff_unix=T0+9600,max_physics_attempts=24))
 for n in ['EXPERIMENT_CONTRACT.json','QUALIFICATION_CONTRACT.json']:shutil.copy2(OLD/n,S/n)
 motion=dict(registered_unix=time.time(),clinical_thresholds=False,reference='new same-seed cold B full TASK; prospective thresholds frozen before any new physical output',primary=dict(burden_ratio=1.10,velocity=['max_abs','p95_abs','rms'],acceleration=['max_abs','p95_abs','rms'],jerk=['p95_abs','rms'],excursion_abs_delta_deg=.5,cumulative_ratio_upper=1.05,cumulative_ratio_lower=.95,endpoint_and_phase_boundary_abs_delta_deg=.5,total_duration_abs_delta_s=.1,each_phase_duration_abs_delta_s=.1,moment_integral_ratio=1.25,tracking_RMS_add_deg=.5,force_peak_ratio=1.05,moment_peak_ratio=1.05,phase_shape_diagnostic_only=True),sensitivity_burden_ratios=[1.,1.05,1.10,1.25],phase_shape_reference_degrees=[.5,1.,2.],jerk_method='dense true dq gradient twice, raw mandatory; SG5/21 order3 sensitivity; no endpoint deletion',basis='10% research noninferiority retains historical moderate tier; .5 degree endpoint/excursion and 5% dose retain historical moderate limits. Add raw acceleration peak and jerk p95/RMS as prospective burden gates. 5% peak compensation and 25% moment integral bounded within unchanged native absolute limits. No evidence supports clinical thresholds; strict/5%/25% reported without reselection.',therapy_trajectory='phase-shape reported separately because broad progress-shape envelope lacks clinical justification; phase goals/boundaries, timing, original tracking and physical hard gates remain mandatory. Full historical PASS/FAIL unchanged.')
 save(S/'MOTION_ACCEPTANCE_PROTOCOL.json',motion)
 (S/'MOTION_ACCEPTANCE_PROTOCOL.md').write_text('# Prospective motion acceptance\n\n'+json.dumps(motion,indent=2,ensure_ascii=False)+'\n')
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/e1e3dc28-50e5-4a6f-91f5-28a37addbaa9/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 rows=json.loads((ROOT/'m2_motion_counterfactual_ranking_v1/COUNTERFACTUAL_BRANCH_RESULTS.json').read_text())['historical_rows'];nonzero=[r for r in rows if np.max(abs(np.asarray(r['x120'])[58:88]))>1e-8];assert len(nonzero)==67
 profiles={}
 for tier in ['strict','moderate','wide']:
  counter=collections.Counter();comb=collections.Counter();individual=[]
  for r in nonzero:
   p=r['motion_profiles'][tier];f=p['failed_requirements'];cats=[]
   for label,pred in [('velocity',lambda s:s.startswith('velocity_')),('acceleration',lambda s:s.startswith('acceleration_')),('dose',lambda s:s in ['actual_excursion','cumulative_angular_travel']),('endpoint_tracking',lambda s:s in ['phase_or_terminal_endpoint','tracking_bounded_change']),('duration',lambda s:s=='task_duration'),('phase_shape',lambda s:s=='phase_progress_q_shape'),('moment',lambda s:s=='moment_integral_bound')]:
    if any(pred(s) for s in f):counter[label]+=1;cats.append(label)
   counter['jerk_optional_failure']+=not p['optional_jerk_screen_pass'];counter['multiple_categories']+=len(cats)>1;comb['+'.join(cats)]+=1
   individual.append(dict(id=r['id'],snapshot=r['snapshot'],candidate_source=r['candidate_source'],failed_requirements=f,categories=cats,optional_jerk_pass=p['optional_jerk_screen_pass'],comparison=p,physical_pass=r['physical_pass']))
  profiles[tier]=dict(denominator=67,counts=dict(counter),combinations=dict(comb),rows=individual)
 save(S/'HISTORICAL_MOTION_FAILURE_AUDIT.json',dict(cohort=80,zero=13,nonzero=67,ordinary=74,historical_G=6,snapshots=13,source_groups=4,new_physics=0,profiles=profiles,source=str(ROOT/'m2_motion_counterfactual_ranking_v1/COUNTERFACTUAL_BRANCH_RESULTS.json'),source_sha256=sha(ROOT/'m2_motion_counterfactual_ranking_v1/COUNTERFACTUAL_BRANCH_RESULTS.json')))
 save(S/'CODE_MANIFEST.json',{str(p.relative_to(S)):sha(p) for d in ['code','deps','native','build','weights','source/stages'] for p in (S/d).rglob('*') if p.is_file()})
 print(json.dumps(dict(prepared=str(S),protected=len(paths),configs=len(configs),historical_counts={k:v['counts'] for k,v in profiles.items()})),flush=True)
if __name__=='__main__':main()
