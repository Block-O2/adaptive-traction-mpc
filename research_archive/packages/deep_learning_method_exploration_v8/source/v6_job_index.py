"""Reviewable per-physical-job START/END, source/config and resource ledger."""
from pathlib import Path
import json,time,datetime,hashlib
P=Path(__file__).resolve().parents[1]
def read(n,d=None):
 q=P/n;return json.loads(q.read_text()) if q.exists() else d
def main():
 ev=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in ev if r['event']=='START'];ends={r['id']:r for r in ev if r['event']=='END'};rows=[]
 for group in sorted(set(r['group'] for r in starts)):
  ss=[r for r in starts if r['group']==group];cfg=read('experiments/'+group+'.json');done=read('jobs/'+group+'/WORKER_DONE.json',{});sup=read('owned/'+group+'_SUPERVISOR.json',{});se=read('owned/'+group+'_SUPERVISOR_END.json',{});manifest=P/'jobs'/group/'SOURCE_MANIFEST.json'
  native=0;partial=[];failed=[]
  for s in ss:
   data=read('runtime/output/'+s['id']+'_DATA.json');par=read('runtime/output/'+s['id']+'_PARTIAL_COMPUTE.json',{});result=read('attempts/'+s['id']+'_RESULT.json',{})
   native+=(data['metric'] if data else par).get('actual_new_native_physics_steps',0)
   if not data:partial.append(dict(id=s['id'],reason=ends.get(s['id'],{}).get('error'),expected_prefix_sampler=ends.get(s['id'],{}).get('expected_prefix_sampler_completion',False)))
   if result.get('qualified') is False:failed.append(dict(id=s['id'],requirements=result.get('motion_vs_B',{}).get('failed_requirements'),error=result.get('error')))
  rows.append(dict(job_id=group,config_sha256=hashlib.sha256((P/'experiments'/f'{group}.json').read_bytes()).hexdigest(),source_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
   source_files=len(read('jobs/'+group+'/SOURCE_MANIFEST.json')['files']),first_physics_START_unix=min(s['unix'] for s in ss),last_physics_END_unix=max([ends[s['id']]['unix'] for s in ss if s['id'] in ends],default=None),
   WORKER_DONE_UTC=done.get('utc'),worker_status=done.get('status'),supervisor_wall_s=se.get('wall_s'),supervisor_exit=se.get('worker_exit_code'),local_job_wall_cap_s=cfg.get('job_wall_cap_s',5400),effective_supervisor_cutoff_unix=sup.get('cutoff_unix'),
   physical_START=len(ss),physical_END=sum(s['id'] in ends for s in ss),actual_new_native_steps=native,partial=partial,failed_candidates=failed,
   resource_limits=dict(original_task_timeout_s=30,native_dt_s=.00025,physics_attempt_wall_timeout_s=read('runtime/RUN_PLAN.json')['physical_timeout_s'],minimum_system_available_RAM_GiB=6,minimum_free_disk_GiB=18,BLAS_OMP_threads=1,physics_owners=1,supervisor_closeout_reserve_s=2400),
   recovery_paths=['jobs/'+group+'/SOURCE_MANIFEST.json','experiments/'+group+'.json','logs/'+group+'_worker.log','logs/'+group+'_RESOURCES.jsonl','jobs/'+group+'/WORKER_DONE.json'],
   hypothesis_and_split=cfg['condition'].get('role',cfg['condition'].get('split')),fork_phase=cfg['fork_phase'],continuation_policy=cfg.get('continuation_policy','commit whole selected policy' if cfg['worker']=='v6_worker.py' else 'see explicit worker/config'),matched_reference_group=cfg.get('matched_reference_group')))
 out=dict(updated_unix=time.time(),jobs=rows,total_physical_START=len(starts),native_steps=sum(r['actual_new_native_steps'] for r in rows),
  note='Physical START/END intervals are measured, not inferred process launches. Parent waiting overlaps child intervals; campaign wall is not their sum. Intentional prefix samplers are incomplete and never successful low-cost tasks. Local protection checks are not cgroups.')
 (P/'JOB_INDEX.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print('JOB_INDEX',len(rows),'jobs',len(starts),'START',flush=True)
if __name__=='__main__':main()
