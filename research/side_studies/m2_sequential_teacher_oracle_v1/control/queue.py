from pathlib import Path
import json,copy,sys,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
def put(n,x):(S/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
cat={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
def spec(v,shape='flat'):
 return dict(kind='PWL',amplitude=v,shape=shape,knots=[.001,.5,.999] if shape=='flat' else [.1,.4,.7],values=[v,v,v] if shape=='flat' else [v,v*.6,v*.2],support=[0,1],domain='remaining_causal_progress')
def modified(c,ident,ph,slot,v,shape='flat'):
 d=copy.deepcopy(c);d.update(id=ident,stage=MODE,parameters=dict(family=MODE,source=c['id'],phase=ph,slot=slot,amplitude=v,shape=shape));d.setdefault('phases',{}).setdefault(ph,[None]*5)[slot]=spec(v,shape) if v else None;return d
MODE=sys.argv[1]
if MODE=='baseline':
 cs=[dict(id='B0_repeat_1',stage='REFERENCE',phases={}),dict(id='B0_repeat_2',stage='REFERENCE',phases={})]+[cat[i] for i in ['NATIVE_SCALAR_18','M2_fixed_actions','C2_pair_1_2','repair2_2_0']]+[dict(id='Frozen_M2',stage='REFERENCE',parameters={'frozen_Q':True})]
 q=dict(candidates=cs)
elif MODE=='outbound':
 cs=[]
 for slot in [0,2,3]:
  for v in [-.02,-.006,.006,.02]:cs.append(modified(cat['NATIVE_SCALAR_18'],f'O{slot}_{v:+.3f}','OUTBOUND',slot,v))
 for slot in [1,4]:
  for v in [-.012,.012]:cs.append(modified(cat['NATIVE_SCALAR_18'],f'O{slot}_{v:+.3f}','OUTBOUND',slot,v,'taper'))
 q=dict(candidates=cs)
else:raise ValueError(MODE)
q['registered_unix']=time.time();put('queue/'+MODE+'.json',q)
print(json.dumps(dict(mode=MODE,candidates=len(q['candidates']))))
