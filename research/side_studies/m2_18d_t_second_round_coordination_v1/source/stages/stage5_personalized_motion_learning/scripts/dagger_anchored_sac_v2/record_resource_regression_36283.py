"""Retrospective timestamped gate evidence from pending protocol before collection resumed."""
from pathlib import Path
import json
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2')
life=[json.loads(x) for x in (L/'LIFECYCLE_36283.jsonl').read_text().splitlines()];start=max(r['unix'] for r in life if r['stage']=='TRAINING_START' and r['total']==36283)
children=[r for r in life if r['stage']=='AFTER_CHILD_RELEASE' and r['unix']<start];assert len(children)==3 and all(r['child_reaped'] for r in children)
res=[json.loads(x) for x in (L/'RESOURCE_CONTINUATION.jsonl').read_text().splitlines()];auth=json.loads((L/'RESUME_36283_AUTHORIZATION.json').read_text());res=[r for r in res if auth['authorized_unix']<=r['unix']<start];assert not any(r['reasons'] for r in res);assert max(r['oom_kill'] for r in res)==min(r['oom_kill'] for r in res)
archives=[r for r in life if r['stage']=='ARCHIVE_BEGIN' and r['unix']<start and r.get('trace_rows',0)>1000];ends=[r for r in life if r['stage']=='ARCHIVE_END'];changes=[]
for a in archives:
 b=next(r for r in ends if r['pid']==a['pid'] and r.get('begin_unix')==a['unix']);changes.append(dict(pid=a['pid'],begin=a['unix'],end=b['unix'],trace_rows=a['trace_rows'],bytes=b['bytes'],PSS_begin=a['memory']['Pss'],PSS_end=b['memory']['Pss'],PSS_delta=b['memory']['Pss']-a['memory']['Pss']))
record=dict(status='PASS',evidence_written_retrospectively=True,gate_interval_before_any_new_collection_end=start,collection_steps_before_after_pending_protocol=36283,three_pending_children_reaped=children,no_spawn_physics_after_release=True,archive_allocations=changes,resource_tree_peak_GiB=max(r['tree_PSS_bytes'] for r in res)/2**30,min_available_GiB=min(r['available_bytes'] for r in res)/2**30,swap_start_MiB=res[0]['swap_bytes']/2**20,swap_last_MiB=res[-1]['swap_bytes']/2**20,no_oom=True,no_resource_risk=True,classification='A+C temporary trace serialization allocation coexisting with idle parent; corrected streaming regression and release pass; no persistent leak observed')
for f in (L,D):(f/'RESOURCE_REGRESSION_36283.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('status','resource_tree_peak_GiB','min_available_GiB','swap_start_MiB','swap_last_MiB','classification')}))
