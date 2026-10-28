from pathlib import Path
import json,hashlib,time,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5';old=json.loads((P/'models/WHOLE_HISTORY_RISK_V5_FROZEN.json').read_text());rows=json.loads((P/'data/WHOLE_HISTORY_RISK_ROWS_V5.json').read_text());parent={r['state_family']:r['state_family'] for r in rows}
def find(x):
 while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
 return x
def union(a,b):
 a,b=find(a),find(b)
 if a!=b:parent[b]=a
hashes={};detail=[]
for g in sorted(set(r['job_group'] for r in rows)):
 source=next(r for r in rows if r['job_group']==g);bdata=json.loads((V/'runtime/output'/f'{g}_B_DATA.json').read_text());at=bdata['child']['physical_time_at_fork'];path=V/'runtime/source/results'/f'{g}_B'/'trace.npz';h=hashlib.sha256()
 with np.load(path) as z:
  use=(z['stage']=='TASK')&(z['time_s']<at-1e-9)
  for key in ['time_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm','task_beta']:
   values=z[key]
   if len(values)==len(use):values=values[use]
   elif len(values)==int(np.sum(z['stage']=='TASK')):values=values[z['time_s'][z['stage']=='TASK']<at-1e-9]
   else:raise ValueError('UNALIGNED_PREFIX_FIELD:'+g+':'+key)
   h.update(key.encode());h.update(np.round(values,10).tobytes())
 fingerprint=h.hexdigest();fam=source['state_family']
 if fingerprint in hashes:union(fam,hashes[fingerprint])
 else:hashes[fingerprint]=fam
 detail.append(dict(group=g,configured_family=fam,actual_shared_prefix_fingerprint=fingerprint,fork_physical_s=at))
merged={f:find(f) for f in parent};count=len(set(merged.values()));out=dict(status='PASS' if count==old['state_families'] else 'ADDITIONAL_ALIAS_MERGE_REQUIRED',configured_families=old['state_families'],actual_prefix_unioned_families=count,rows=detail,union_mapping=merged,rounding_units=1e-10,scope='complete executed pre-fork TASK observer/physical/reference/torque/belief history; future outcomes and current candidate action excluded; never split a configured family')
(P/'audit/ACTUAL_PREFIX_RISK_PARENT_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print('ACTUAL_PREFIX_GROUPS',old['state_families'],'->',count,flush=True)
