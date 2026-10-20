from task_bootstrap import *
import numpy as np
def main():
 pools={};sources=[];issues=[];parent_splits={};exposure={}
 for p in sorted((STUDY/'output').glob('*_DATA.json')):
  r=json.loads(p.read_text());sources.append(dict(id=r['id'],path=str(p),sha256=sha(p),split=r['split'],group=r['group'],complete_valid=r['metric']['valid'],continuation=r['continuation'],input_dim=len(r['branch_start']['input']),information='causal commissioned estimated B'))
  parent_splits.setdefault(r['group'],set()).add(r['split']);snapshot=r['child']['snapshot_hash'];pools.setdefault(snapshot,[]).append(r)
  if len(r['branch_start']['input'])!=120:issues.append(dict(id=r['id'],issue='INPUT_DIM'))
  if r['remaining_J_F']<0:issues.append(dict(id=r['id'],issue='NEGATIVE_REMAINING_COST'))
  c=np.asarray(r['branch_start']['context']['observation']);key=np.round(c,4).tobytes();exposure.setdefault(key,[]).append(r['group'])
 rows=[]
 for snapshot,pool in pools.items():
  valid=[r for r in pool if r['metric']['valid']];first=pool[0];ctx=first['branch_start']['context'];costs=[r['remaining_J_F'] for r in valid];moments=[r['remaining_M'] for r in valid]
  rows.append(dict(snapshot=snapshot,group=first['group'],split=first['split'],phase=ctx['phase'],task_s=ctx['task_s'],branches=len(pool),valid=len(valid),remaining_cost_range_N_s=float(np.ptp(costs)) if costs else None,remaining_cost_min=min(costs) if costs else None,remaining_cost_max=max(costs) if costs else None,moment_range=float(np.ptp(moments)) if moments else None,source_labels=[r['branch_start']['source'] for r in pool]))
 result=dict(updated_unix=time.time(),status='PASS' if not issues and all(len(s)==1 for s in parent_splits.values()) else 'FAIL',issues=issues,parent_splits={k:list(v) for k,v in parent_splits.items()},registered_pools=len(pools),distinct_causal_55D_state_groups=len(exposure),cross_parent_repeated_state_groups=[sorted(set(v)) for v in exposure.values() if len(set(v))>1],rows=rows,sources=sources,labels='actual full repetition metric minus measured causal prefix; failed trajectories not low-cost successes',truth_firewall='candidate features contain estimated observations/reference/commissioned beta, no evaluation truth state or future cost; Q uses direct executed labels only',generalization='one exposed Human, repeated initial states excluded from dev/train and nominal replicated test overlap excluded from training; adjacent native samples not independent scenes')
 save(STUDY/'DATASET_AUDIT.json',result);print(json.dumps({k:result[k] for k in ('status','registered_pools','distinct_causal_55D_state_groups','cross_parent_repeated_state_groups')}))
if __name__=='__main__':main()
