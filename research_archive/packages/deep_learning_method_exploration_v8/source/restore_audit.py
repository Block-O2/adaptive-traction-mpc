from pathlib import Path
import hashlib,json,time
V=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');P=Path(__file__).resolve().parents[1]
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):(P/'audit'/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
t=time.time();m=json.loads((V/'OUTPUT_MANIFEST.json').read_text());errors=[];n=0;total=0
for rel,d in m['files'].items():
 f=V/rel;n+=1
 if not f.exists() or f.stat().st_size!=d['bytes'] or sha(f)!=d['sha256']:errors.append(rel)
 total+=d['bytes']
put('V5_MANIFEST_RESTORE.json',{'status':'PASS' if not errors else 'FAIL','files':n,'bytes':total,'mismatches':errors,'wall_s':time.time()-t,'manifest_sha256':sha(V/'OUTPUT_MANIFEST.json'),'read_only':True})
# Read full ledger without treating summary as a substitute for per-attempt records.
a=json.loads((V/'RESOURCE_AND_ATTEMPT_ACCOUNTING.json').read_text())
c=json.loads((V/'experiments/VAL01.json').read_text());ids=['HANDOFF01_BEST','HANDOFF01_BOTHLOW','OPT01_PATTERN011','COMPOSE01_PAIR01','STRICT01_ANT']
rows=[]
for ident in ids:
 r=json.loads((V/'attempts'/f'{ident}_RESULT.json').read_text());met=json.loads((V/r['metrics_path']).read_text());rows.append({'id':ident,'qualified':r['qualified'],'action':r['action'],'JF':r['JF'],'JM':r['JM'],'jerk_RMS_deg_s3':met['motion']['raw']['full']['jerk_deg_s3']['rms'],'axes':r['axes'],'raw_sources':met['sources'],'action_sha256':hashlib.sha256(json.dumps(r['action'],sort_keys=True).encode()).hexdigest(),'motion_failed':r['motion_vs_B']['failed_requirements']})
put('V5_RECOVERED_BASELINES.json',{'rows':rows,'library':{x['tag']:x['action'] for x in c['actions'] if x['tag'] in ['BEST','HANDOFF','PATTERN','COMPOSE','ANTICIPATORY']},'v5_accounting':{'START':a['physical_START'],'END':a['physical_END'],'native_steps':a['actual_new_native_steps']},'not_new_experiments':True})
print('RESTORE',n,'errors',len(errors),'wall',time.time()-t,flush=True)
