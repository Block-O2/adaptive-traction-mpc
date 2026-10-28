"""Evaluate effective reference/physics identities, not proposal labels."""
from pathlib import Path
import json,os,sys,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];g=sys.argv[1];rows=[]
def digest_arrays(z,keys,mask):
 h=hashlib.sha256()
 for k in keys:
  v=np.ascontiguousarray(z[k][mask]);h.update(k.encode());h.update(str(v.dtype).encode());h.update(str(v.shape).encode());h.update(v.tobytes())
 return h.hexdigest()
for f in sorted((P/'attempts').glob(g+'_*_RESULT.json')):
 r=json.loads(f.read_text());id=r['id']
 if not r['complete']:continue
 snap=json.loads((P/'runtime/reports'/f'{id}_SNAPSHOT.json').read_text());fork=r['branch']['physical_time_s']
 with np.load(P/'runtime/source/results'/id/'trace.npz') as z:
  task=z['stage']=='TASK';prefix=(z['time_s']<fork-1e-9);keys=['time_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm']
  physical=digest_arrays(z,keys,task);ref=digest_arrays(z,['time_s','reference_q_rad','reference_dq_rad_s'],task);prior=digest_arrays(z,keys,prefix)
  before=np.flatnonzero(prefix)[-1];causal=z['estimated_human_state_rad_rad_s'][before].tolist()
 rows.append({'id':id,'native_integration_sha256':snap['manifest']['native_integration']['sha256'],'full_controller_state_hash':snap['hash'],'actual_prefork_trace_fingerprint':prior,'last_prefork_causal_state':causal,'accepted_reference_fingerprint':ref,'actual_physical_trace_fingerprint':physical,'qualified_original':r['qualified'],'JF':r['JF'],'JM':r['JM']})
assert len({r['native_integration_sha256'] for r in rows})==1,'MIXED_PHYSICAL_PARENTS';assert len({r['actual_prefork_trace_fingerprint'] for r in rows})==1,'MIXED_PREFIX_PHYSICS'
aliases={}
for r in rows:aliases.setdefault(r['actual_physical_trace_fingerprint'],[]).append(r['id'])
result={'group':g,'evaluated_unix':time.time(),'same_actual_physical_parent':True,'same_prefork_trace':True,'rows':rows,'complete_proposals':len(rows),'unique_accepted_reference_traces':len({r['accepted_reference_fingerprint'] for r in rows}),'unique_actual_physical_traces':len(aliases),'physical_alias_groups':[ids for ids in aliases.values() if len(ids)>1],'scope':'All variants remain one exposed development parent, regardless labels; native integration and pre-fork trace checked separately from full hash/config/RNG. No new-state generalization from repeated jobs.'}
q=P/'analysis'/(g+'_ACTUAL_ACTION_IDENTITIES.json');tmp=q.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(q);print('ACTION_IDENTITIES',g,'complete',len(rows),'effective_physics',len(aliases),'aliases',result['physical_alias_groups'])
