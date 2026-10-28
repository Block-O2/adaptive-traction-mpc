from pathlib import Path
import os,json,hashlib,shutil,datetime,subprocess,time,sys
ROOT=Path('/home/hank/ihear-lab');OLD=ROOT/'learning_guided_motion_improvement_v1'
now=datetime.datetime.now(datetime.timezone.utc);P=ROOT/'autonomous_coordination_learning_v2'
if P.exists():P=ROOT/('autonomous_coordination_learning_v2_'+now.strftime('%Y%m%dT%H%M%SZ')+'_'+str(os.getpid()))
P.mkdir();Path('/tmp/acl2_active_package').write_text(str(P))
for d in ['source','audit','logs','attempts','predictions','models','history','figures','jobs','owned','queue','runtime']:(P/d).mkdir()
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
shutil.copyfile('/home/hank/.codex/attachments/3f7fb946-196d-41db-9adb-ae63a85e1ef2/Pasted text.txt',P/'USER_REQUEST.txt')
shutil.copyfile(__file__,P/'source/bootstrap.py')
records={};dirs=[d for d in ROOT.iterdir() if d.is_dir() and d!=P]
for top in dirs:
 for base,ds,fs in os.walk(top):
  ds[:]=[x for x in ds if x not in ['cpu-env','offline-env','.venv','venv','__pycache__','.git','node_modules']]
  for n in fs:
   f=Path(base)/n
   if f.is_symlink():continue
   st=f.stat();row={'size':st.st_size,'mtime_ns':st.st_mtime_ns}
   if f.suffix in ['.py','.xml','.so','.pt','.zip'] or n in ['REPORT.md','AGENTS.md'] or 'MANIFEST' in n or 'CONTRACT' in n:row['sha256']=sha(f)
   records[str(f)]=row
put('audit/HISTORY_START.json',records)
G=ROOT/'rl_b_matched_recovery_stability_v1/github'
put('audit/GIT_START.json',{'head':subprocess.check_output(['git','-C',str(G),'rev-parse','HEAD'],text=True).strip(),'branch':subprocess.check_output(['git','-C',str(G),'branch','--show-current'],text=True),'status':subprocess.check_output(['git','-C',str(G),'status','--porcelain=v1','--untracked-files=all'],text=True),'index_sha256':sha(G/'.git/index')})
for d in ['source','control','code','deps']:
 shutil.copytree(OLD/'runtime'/d,P/'runtime'/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for d in ['output','reports','audit','tmp','motion_series','source/results']:(P/'runtime'/d).mkdir(parents=True,exist_ok=True)
for f in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','ACTION_SET.json','FROZEN_SELECTION.json']:
 shutil.copyfile(OLD/'runtime'/f,P/'runtime'/f)
relocations=[]
for d in ['source','control','code','deps']:
 for f in (P/'runtime'/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.toml','.yaml','.yml']:continue
  try:s=f.read_text()
  except UnicodeError:continue
  s2=s.replace(str(OLD/'runtime'),str(P/'runtime'))
  if s2!=s:
   before=sha(f);f.write_text(s2);relocations.append({'path':str(f.relative_to(P)),'before':before,'after':sha(f)})
for f in ['RECOVERY_TEST_PLAN.json','OPTIMIZATION_TEST_PLAN.json']:
 shutil.copyfile(OLD/'runtime'/f,P/'history'/f)
for f in ['nominal_proxy.py','independent_audit.py']:
 shutil.copyfile(OLD/'source'/f,P/'source'/('legacy_'+f))
for f in ['CAUSAL_COMMISSIONED_BELIEF.json','CAUSAL_H150_REFERENCE_TEMPLATE.npz']:
 if (OLD/'history'/f).exists():shutil.copyfile(OLD/'history'/f,P/'history'/f)
put('audit/CLOSURE_RELOCATION.json',{'origin':str(OLD),'origin_manifest_sha256':sha(OLD/'CAMPAIGN_SOURCE_MANIFEST.json'),'relocations':relocations,'historical_file_count':len(records),'no_scientific_changes_in_copied_runtime':True})
put('audit/JOURNAL_START_SNAPSHOT.json',{'sha256':sha(ROOT/'RESEARCH_DECISION_JOURNAL.md'),'size':(ROOT/'RESEARCH_DECISION_JOURNAL.md').stat().st_size})
shutil.copyfile(ROOT/'RESEARCH_DECISION_JOURNAL.md',P/'history/JOURNAL_BEFORE.md')
print(json.dumps({'package':str(P),'historical_files':len(records),'relocations':len(relocations)},ensure_ascii=False),flush=True)
