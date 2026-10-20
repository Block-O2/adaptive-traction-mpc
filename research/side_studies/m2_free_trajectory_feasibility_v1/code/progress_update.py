from task_bootstrap import *
import numpy as np
def main():
 events=[json.loads(l) for l in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if l.strip()];starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END'];completed={e['id'] for e in ends};tasks={};rows=[]
 account_path=STUDY/'reports/AUDIT_COMPUTE_RECONCILIATION.json';accounts={r['id']:r for r in json.loads(account_path.read_text()).get('rows',[])} if account_path.exists() else {}
 for p in sorted((STUDY/'output').glob('*_RESULT.json')):
  r=json.loads(p.read_text());m=r.get('metric',{});id=r['id'];cfg=r.get('inputs',{});sr=STUDY/'output'/(id+'_SELECTIONS.json');stats={}
  if sr.exists():
   s=json.loads(sr.read_text())['rows']
   if s:stats=dict(coordinator_ms_quantiles=np.quantile([x['end_to_end_s']*1000 for x in s],[.5,.9,.95,1]).tolist(),late_discard=sum(x.get('late_discard',False) for x in s),learning_selected_changes=sum(x.get('plan_changed',False) for x in s),fast_coordinator_ms_quantiles=np.quantile([x.get('fast_coordinator_s',x['end_to_end_s'])*1000 for x in s],[.5,.9,.95,1]).tolist())
  partial=STUDY/'output'/(id+'_PARTIAL_COMPUTE.json');pm=json.loads(partial.read_text()) if partial.exists() else {}
  input_path=STUDY/'queue'/(id+'.json')
  if not input_path.exists():input_path=STUDY/'inputs'/(id+'.json')
  row=dict(id=id,status=r['status'],valid=m.get('valid',False),scientific_version=cfg.get('scientific_version'),timing_version=cfg.get('timing_version'),execution_mode=cfg.get('execution_mode'),wall_seconds=r.get('wall_seconds'),physics_seconds=m.get('actual_new_simulation_seconds',m.get('simulation_seconds',pm.get('simulation_seconds'))),physics_steps=m.get('actual_new_native_physics_steps',m.get('native_physics_steps',pm.get('native_physics_steps'))),absolute_plant_time_s=m.get('simulation_seconds'),J_F=m.get('J_F') if m.get('valid') else None,partial_J_F_unranked=m.get('J_F',pm.get('observed_tick_force_integral')) if not m.get('valid') else None,input_hash=sha(input_path),source_manifest_sha256=cfg.get('source_manifest_sha256'),result_sha256=sha(p),attempt_count=1,**stats)
  account=accounts.get(id,{})
  row.update(physics_snapshot_lower_bound_seconds=row['physics_seconds'],physics_snapshot_lower_bound_steps=row['physics_steps'],terminal_tail_native_steps=account.get('raw_verified_additional_terminal_steps'),raw_verified=account.get('raw_verified_native_steps') is not None,inter_rep_physics_seconds_separate=account.get('inter_rep_physics_seconds',0),inter_rep_native_steps_separate=account.get('inter_rep_native_steps',0))
  if row['raw_verified']:row.update(physics_seconds=account['raw_verified_physics_seconds'],physics_steps=account['raw_verified_native_steps'])
  rows.append(row);tasks[id]=row
 resource=STUDY/'output/RESOURCE_LOG.jsonl';last=json.loads(resource.read_text().splitlines()[-1]) if resource.exists() else {}
 status=dict(elapsed_h=(time.time()-START)/3600,attempts=len(starts),ended=len(ends),active=[e['id'] for e in starts if e['id'] not in completed],results=rows,last_resource=last,next_steps=sys.argv[1] if len(sys.argv)>1 else 'Continue exact acceleration and native scheduling diagnosis; pilot remains conditional.',hard_deadline_unix=START+9*3600,dispatch_cutoff_unix=START+8.25*3600)
 # Runner alone owns TASK_LEDGER while live; detailed evidence is separate.
 save(STUDY/'AUDIT_TASK_LEDGER.json',tasks);save(STUDY/'CHECKPOINT.json',status)
 (STUDY/'PROGRESS.md').write_text('# Progress\n\n'+json.dumps({k:v for k,v in status.items() if k not in ('results','last_resource')},indent=2)+'\n\n'+ '\n'.join(f"- {r['id']}: {r['status']}, VALID={r['valid']}, J_F={r['J_F']}, p50={r.get('coordinator_ms_quantiles')}" for r in rows)+'\n')
 save(STUDY/'reports'/('PROGRESS_'+str(int(time.time()))+'.json'),status)
 print(json.dumps({k:v for k,v in status.items() if k not in ('results','last_resource')}));print(json.dumps(rows[-4:]))
if __name__=='__main__':main()
