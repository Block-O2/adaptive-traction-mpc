from pathlib import Path
import os,json,time,hashlib,subprocess,datetime
S=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime')
def load(name):return json.loads((S/name).read_text())
def put(name,x):(S/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(2**20),b''):h.update(x)
 return h.hexdigest()
def main():
 records=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[x for x in records if x['event']=='START'];table=[]
 for a in starts:
  ident=a['id'];p=S/'output'/(ident+'_DATA.json');q=S/'output'/(ident+'_PARTIAL_COMPUTE.json')
  if p.exists():
   d=json.loads(p.read_text());m=d['metric'];child=d.get('child');inherited=0 if child is None else child['physics_step_at_fork'];full=m['native_physics_steps'];new=m['actual_new_native_physics_steps'];assert full-inherited==new
   row=dict(id=ident,source=str(p),full_archived_steps=full,inherited_steps=inherited,actual_new_steps=new,task_valid=m['task_valid'])
  else:
   m=json.loads(q.read_text());row=dict(id=ident,source=str(q),full_archived_steps=m['native_physics_steps'],inherited_steps=0,actual_new_steps=m['actual_new_native_physics_steps'],task_valid=False)
  table.append(row)
 total=sum(r['actual_new_steps'] for r in table)
 put('ACTUAL_PHYSICAL_WORK_ACCOUNTING.json',dict(attempt_denominator=len(starts),actual_new_native_steps=total,actual_new_simulated_seconds=total*.00025,rows=table,method='post-fork DATA metrics, full archived steps minus inherited complete prefix; failed parent uses preserved partial-compute counter',early_summary_issue='output/ID.json is saved before interface.finish subtracts inherited prefix; it cannot be summed as actual newly computed work'))
 summary=load('SEARCH_SUMMARY.json');old=summary['actual_new_native_steps'];summary['actual_new_native_steps']=total;summary['physical_work_accounting_path']=str(S/'ACTUAL_PHYSICAL_WORK_ACCOUNTING.json');put('SEARCH_SUMMARY.json',summary)
 audit=load('RESOURCE_AND_STORAGE_AUDIT.json');audit['actual_new_native_steps']=total;audit['actual_new_simulated_seconds']=total*.00025;audit['accounted_attempts']=len(table);audit['total_package_bytes_before_final_manifest']=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());audit['file_cache_advice_audit']=str(S/'FILE_CACHE_ADVICE.jsonl');put('RESOURCE_AND_STORAGE_AUDIT.json',audit)
 ver=load('PACKAGE_VERIFICATION.json');assert ver['status']=='PASS';ver['actual_work_accounting_all_attempts']=len(table)==len(starts);ver['actual_new_native_steps']=total;ver['selection_unchanged_since_heldout_start']=load('FROZEN_SELECTION.json')['unix']<min(r['unix'] for r in starts if r['id'].startswith(('H1_','H2_')))
 required=['REPORT.md','SEARCH_PROTOCOL.json','ACTION_SPACE_MAP.md','ACTION_SPACE_MAP.json','CANDIDATE_CATALOG.json','SEARCH_SUMMARY.json','FORCE_MOTION_PARETO.json','PHASE_ATTRIBUTION.md','PHASE_ATTRIBUTION.json','NATIVE_EXECUTION_LINEAGE.json','VALIDATION_RESULTS.json','RESOURCE_AND_STORAGE_AUDIT.json','PACKAGE_VERIFICATION.json']
 ver['required_deliverables']={name:(S/name).exists() for name in required};assert all(ver['required_deliverables'].values());assert len(starts)<=160
 commands=dict(python='/home/hank/envs/adaptive-online-rl-v1/bin/python',cwd=str(S),commands=['prepare.py (Windows control script, creates isolated Linux package)','code/register_search.py','static native pool/load/graph validation (0 physical attempts)','code/search_driver.py discovery (failed parent wrapper, all evidence retained)','code/search_driver.py resume (same case/seed, two-zero + old/new exact gates, no repeat failed candidate)','code/freeze_representatives.py (pre-heldout bookkeeping only)','code/search_driver.py H1','code/search_driver.py H2','code/finalize_search.py','code/plot_search.py','code/close_search.py'],Q_or_Neural_Q_training=0,host_clock_campaigns=0,global_WSL_config_changes=0,Git_mutations=0)
 put('COMMANDS_AND_REVISIONS.json',commands)
 report=(S/'REPORT.md').read_text().replace(f'新增物理步 **{old}**',f'新增物理步 **{total}**')
 report+='\n\n实际工作量计数从每次 fork 后的 DATA 记录核验，排除归档 trace 中继承的完整前缀：'+str(total)+' 个新增 native steps（'+str(total*.00025)+' s 新增模拟物理时间）。早期 ID.json 保存先于 finish 的前缀扣除，已修正汇总；原 J_F、motion、任务与验证结果未改变。逐attempt完整/继承/新计算步数见 ACTUAL_PHYSICAL_WORK_ACCOUNTING.json。\n\n![Force–motion search](FORCE_MOTION_SEARCH.png)\n'
 (S/'REPORT.md').write_text(report)
 closed=dict(status='COMPLETE',scientific_status=summary['status'],recommendation='A',attempts=len(starts),physics_workers_exited=ver['workers_exited'],unix=time.time(),Asia_Shanghai=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),elapsed_h=(time.time()-audit['start_unix'])/3600,no_automatic_followup=True,no_Q_training=True,no_host_clock_qualification=True)
 assert closed['unix']<audit['hard_stop_unix'];put('PACKAGE_CLOSED.json',closed);audit['final_close_unix']=closed['unix'];audit['final_elapsed_wall_s']=closed['unix']-audit['start_unix'];put('RESOURCE_AND_STORAGE_AUDIT.json',audit);put('PACKAGE_VERIFICATION.json',ver)
 manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name!='FINAL_MANIFEST.json'};put('FINAL_MANIFEST.json',manifest)
 print(json.dumps(dict(closed=closed,actual_new_steps=total,verification=ver['status'],manifest_files=len(manifest))),flush=True)
if __name__=='__main__':main()
