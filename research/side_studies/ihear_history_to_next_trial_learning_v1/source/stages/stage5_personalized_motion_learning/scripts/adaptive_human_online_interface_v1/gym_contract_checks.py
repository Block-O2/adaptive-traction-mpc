"""API-only terminal mapping checks; no physics or training is started here."""
from pathlib import Path
import sys,json
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_history_to_next_trial_learning_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_gym import DirectOnlineSmokeEnv
rows=[]
for status,reason,expected in [('COMPLETE',None,(True,False)),('ABORTED','TIMEOUT_OUTBOUND',(False,True)),('ABORTED','FORCE_LIMIT',(True,False))]:
    env=DirectOnlineSmokeEnv(S/'results/adaptive_human_online_interface_v1/gym/api_only_unused',{},{});env.pending=True
    env.events.put(('terminal',None,dict(status=status,abort_reason=reason)))
    obs,reward,terminated,truncated,info=env.step(np.zeros(2))
    assert (terminated,truncated)==expected and not env.pending and reward==0.
    rows.append(dict(status=status,abort_reason=reason,terminated=terminated,truncated=truncated,pass_=True,scope='injected terminal event API mapping only; no physical rollout'))
    env.close()
p=D/'DIRECT_RL_GYM_READINESS.json';data=json.loads(p.read_text());data['terminal_mapping_probes']=rows
p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');print(json.dumps({'terminal_mapping_checks':len(rows),'passed':len(rows)}))
