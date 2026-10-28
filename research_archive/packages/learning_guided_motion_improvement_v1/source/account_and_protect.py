"""Close actual attempt/native/resource and historical-protection ledgers."""
from pathlib import Path
import os,json,hashlib,datetime,subprocess,collections,time
P=Path(__file__).resolve().parents[1];R=P/'runtime';G=P.parent/'rl_b_matched_recovery_stability_v1/github'
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as s:
  for x in iter(lambda:s.read(4*2**20),b''):h.update(x)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
 events=[json.loads(x) for x in (R/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];endmap={r['id']:r for r in ends};audit=json.loads((P/'audit/INDEPENDENT_RAW_AUDIT.json').read_text());rawmap={r['id']:r for r in audit['rows']};rows=[];unknown=[]
 for r in starts:
  ident=r['id'];a=rawmap[ident];new=a.get('actual_new_native_steps')
  if new is None and a.get('partial_compute'):new=a['partial_compute'].get('actual_new_native_physics_steps')
  if new is None:unknown.append(ident)
  e=endmap.get(ident);rows.append({'id':ident,'category':r.get('category'),'START_unix':r['unix'],'END_unix':None if e is None else e['unix'],'joined':False if e is None else e.get('joined',False),'returncode':None if e is None else e.get('returncode'),'actual_new_native_steps':new,'complete_independent_audit':a['status']=='PASS','wall_start_end_s':None if e is None else e['unix']-r['unix']})
 duplicate=len(starts)!=len({r['id'] for r in starts});category=dict(collections.Counter(r.get('category','UNSPECIFIED') for r in starts));native=sum(r['actual_new_native_steps'] or 0 for r in rows);unclosed=[r['id'] for r in rows if r['END_unix'] is None or not r['joined']]
 counts={'physical_attempts':len(starts),'optimization':category.get('optimization',0),'validation':category.get('validation',0),'engineering':category.get('engineering',0),'actual_new_native_steps':native}
 limits=json.loads((P/'START.json').read_text())['limits'];budget_pass=len(starts)<=80 and counts['optimization']<=60 and counts['validation']<=12 and counts['engineering']<=8 and native<=8000000 and not unknown
 accounting={'status':'PASS' if budget_pass and not duplicate and not unclosed else 'FAIL','counts':counts,'limits':limits,'category_counts':category,'rows':rows,'unknown_native_attempts':unknown,'unclosed':unclosed,'duplicate_START':duplicate,'all_failures_in_denominator':True,'import_only_launch_failures':{'physical_native_steps':0,'logs':['logs/recovery.log','logs/recovery_v2.log','logs/recovery_v3.log'],'not_physical_STARTs':True},'native_accounting':'cold parent includes its newly executed prefix and suffix; each fork child counts actual native steps after fork, inherited raw prefix not recounted as new physics; full task JF still includes the identical physically executed prefix'}
 put('ATTEMPT_ACCOUNTING.json',accounting)
 samples=[json.loads(x) for x in (P/'audit/RESOURCE_SAMPLES.jsonl').read_text().splitlines()];stat=[f.stat().st_size for f in P.rglob('*') if f.is_file()];t0=datetime.datetime.fromisoformat(json.loads((P/'START.json').read_text())['T0_utc']).timestamp();last_end=max(r['unix'] for r in ends);now=time.time();span=last_end-min(r['unix'] for r in starts)
 resource={'status':'PASS' if min(s['available_ram_bytes'] for s in samples)>=6*2**30 and min(s['disk_free_bytes'] for s in samples)>=12*2**30 else 'FAIL','min_available_ram_gib':min(s['available_ram_bytes'] for s in samples)/2**30,'min_disk_free_gib':min(s['disk_free_bytes'] for s in samples)/2**30,'disk_free_drop_gib':(samples[0]['disk_free_bytes']-samples[-1]['disk_free_bytes'])/2**30,'package_bytes_at_accounting':sum(stat),'max_owned_worker_processes':max(len(s['owned_physics']) for s in samples),'parallel_physics_environments':1,'quiescent_parent_note':'one parent pauses in waitpid while exactly one child advances native physics; two owned processes does not mean two active physics environments','actual_elapsed_hours_at_accounting':(now-t0)/3600,'physical_queue_elapsed_hours_from_activation':(last_end-t0)/3600,'physical_queue_span_hours':span/3600,'native_per_queue_wall_s':native/span,'throughput_scope':'includes commissioning, archival, scoring, model fitting and gaps; not ideal mj_step speed','sample_count':len(samples),'no_server_resize':True,'no_dependency_install':True}
 put('RESOURCE_USAGE.json',resource)
 # Compare every protected old file's metadata and every preregistered content hash.
 before=json.loads((P/'audit/HISTORY_START.json').read_text());changes=[];checked=0;hashed=0
 for path,entry in before.items():
  f=Path(path)
  if not f.exists():changes.append({'path':path,'error':'MISSING'});continue
  st=f.stat();checked+=1
  if st.st_size!=entry['size'] or st.st_mtime_ns!=entry['mtime_ns']:changes.append({'path':path,'error':'SIZE_OR_MTIME_CHANGED'})
  if 'sha256' in entry:
   hashed+=1
   if sha(f)!=entry['sha256']:changes.append({'path':path,'error':'CONTENT_CHANGED'})
 after_paths=set()
 for root in P.parent.glob('rl_b_*'):
  if not root.is_dir():continue
  for base,dirs,files in os.walk(root):
   dirs[:]=[d for d in dirs if d not in ['cpu-env','offline-env','.venv','venv','__pycache__','.git','node_modules']]
   for name in files:
    ff=Path(base)/name
    if ff.is_file() and not ff.is_symlink():after_paths.add(str(ff))
 additions=sorted(after_paths-set(before))
 for path in additions:changes.append({'path':path,'error':'NEW_FILE_IN_PROTECTED_OLD_PACKAGE'})
 old=json.loads((P/'audit/GIT_START.json').read_text());env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');git={'head':subprocess.check_output(['git','-C',str(G),'rev-parse','HEAD'],env=env,text=True).strip(),'branch':subprocess.check_output(['git','-C',str(G),'branch','--show-current'],env=env,text=True),'status':subprocess.check_output(['git','-C',str(G),'status','--porcelain=v1','--untracked-files=all'],env=env,text=True),'index_sha256':sha(G/'.git/index')};same=git==old
 put('audit/HISTORY_END.json',{'status':'PASS' if not changes and same else 'FAIL','old_files_checked':checked,'old_files_content_hashed':hashed,'changes':changes,'git_unchanged':same,'git':git,'no_commit_push_merge_reset_stash_clean':True})
 # Owned process audit uses exact script arguments, never unrelated PIDs.
 scripts={str(P/'source'/n) for n in ['recovery_worker.py','study_worker.py','validation_worker.py','monitor.py','finish_when_ready.py','independent_audit.py','analyze_results.py','posthoc_mechanism.py']};alive=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   cmd=[x.decode(errors='replace') for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
   if cmd and 'python' in Path(cmd[0]).name and any(x in scripts for x in cmd):alive.append({'pid':int(proc.name),'argv':cmd,'start_ticks':(proc/'stat').read_text().split()[21]})
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 put('audit/PROCESS_EXIT_AUDIT.json',{'status':'PASS' if not alive and not unclosed else 'FAIL','alive_owned':alive,'ledger_unclosed':unclosed,'all_START_END_joined':not unclosed,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 print(json.dumps({'counts':counts,'budget_pass':budget_pass,'history_changes':len(changes),'git_same':same,'owned_alive':len(alive)}),flush=True)
if __name__=='__main__':main()
