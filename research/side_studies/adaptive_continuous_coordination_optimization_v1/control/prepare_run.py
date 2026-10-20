from pathlib import Path
import json,shutil,hashlib,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
old=P.parent/'adaptive_continuous_coordination_interface_v1'
shutil.copy2(old/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
if (P/'logs/campaign.log').exists():shutil.copy2(P/'logs/campaign.log',P/'audit/startup_failure_before_physics.log')
adaptive=json.loads((P/'ADAPTIVE_REFINEMENT_PLAN.json').read_text())['internal_fraction'];adaptive=.25 if abs(adaptive-.5)<.05 else adaptive
def c(i,f,fr=None,de=None,ti=None,legacy=None):
 s=None if fr is None else dict(fractions=fr,deltas_deg=de)
 if ti is not None:s['time_fractions']=ti
 return dict(id=i,family=f,spec=s,legacy_delta=legacy or [0,0],waypoint_count=0 if f=='B' else 3 if fr is None else len(fr))
rows=[c('B0','B'),c('legacy002','P',legacy=[0,.02]),c('legacy005','P',legacy=[0,.05]),c('legacy005_repeat','P',legacy=[0,.05]),c('D1_knee_pos','P',[.5],[[0,.02]]),c('D1_knee_neg','P',[.5],[[0,-.02]]),c('D1_hip_pos','P',[.5],[[.02,0]]),c('D1_hip_neg','P',[.5],[[-.02,0]]),c('D1_coupled','P',[.5],[[.02,-.02]]),c('D1_coupled_inverse','P',[.5],[[-.02,.02]]),c('D2_knee_uniform','P',[1/3,2/3],[[0,.02],[0,.02]]),c('D2_knee_alternating','P',[1/3,2/3],[[0,.02],[0,-.02]]),c('D3_knee_uniform','P',[.25,.5,.75],[[0,.02],[0,.02],[0,.02]]),c('D3_knee_alternating','P',[.25,.5,.75],[[0,.02],[0,-.02],[0,.02]]),c('adaptive_D2','P',sorted([.5,adaptive]),[[0,.01],[0,.02]]),c('S_fixed_knots_early','S_PROXY',[.5],[[0,0]],[.4995]),c('S_fixed_knots_late','S_PROXY',[.5],[[0,0]],[.5005]),c('PS_early','P+S_PROXY',[.5],[[.02,-.02]],[.4995])]
(P/'CANDIDATE_PLAN.json').write_text(json.dumps(dict(frozen_unix=time.time(),coarse=rows,refinement='one deterministic repeat if force improves and motion PASS and velocity TV <=1.01 B',validation='only new force record below 1400.697221 with complete PASS; primary frozen before paired validation'),indent=2))
manifest={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in str(f)}
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(unix=time.time(),files=manifest,plan_sha256=hashlib.sha256((P/'CANDIDATE_PLAN.json').read_bytes()).hexdigest(),motion_contract_sha256=hashlib.sha256((P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest()),indent=2));print('FROZEN',len(rows),len(manifest))
