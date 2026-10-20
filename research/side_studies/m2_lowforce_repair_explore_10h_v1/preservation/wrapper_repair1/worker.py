from study_common import *
import matched_harness as mh
import analyze_matched as am
import search_driver as sd
import copy,random,signal,traceback,resource
S=STUDY; P=json.loads((S/'SEARCH_PROTOCOL.json').read_text()); ZERO=np.zeros((2,5,3))
MODE=sys.argv[1]
def put(n,x):mh.put(S/n,x)
def events():return mh.records()
def append(n,x):
 with (S/n).open('a') as f:f.write(json.dumps(clean(x),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def resource_check():
 mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()};disk=shutil.disk_usage('/mnt/d');size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());row=dict(unix=time.time(),pid=os.getpid(),linux_available_bytes=mem['MemAvailable'],swap_used_bytes=mem['SwapTotal']-mem['SwapFree'],D_free_bytes=disk.free,package_bytes=size)
 try:
  import subprocess
  win=subprocess.run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command','Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Compress'],capture_output=True,text=True,timeout=20)
  row['windows_memory']=json.loads(win.stdout) if win.returncode==0 else {'status':'UNAVAILABLE','returncode':win.returncode}
 except Exception as e:row['windows_memory']={'status':'UNAVAILABLE','reason':str(e)}
 append('RESOURCE_SAMPLES.jsonl',row)
 if row['windows_memory'].get('FreePhysicalMemory') is not None:assert row['windows_memory']['FreePhysicalMemory']*1024>=2**30,'RESOURCE_WINDOWS_MEMORY'
 assert disk.free>=40*2**30,'RESOURCE_D_SPACE';assert size<20*2**30,'RESOURCE_STORAGE';assert mem['MemAvailable']>=2**30,'RESOURCE_MEMORY'
 past=[json.loads(l) for l in (S/'RESOURCE_SAMPLES.jsonl').read_text().splitlines()][-3:]
 assert not(len(past)==3 and all(r['linux_available_bytes']<2*2**30 for r in past)),'RESOURCE_SUSTAINED_MEMORY'
 assert not(len(past)==3 and past[-1]['swap_used_bytes']-past[0]['swap_used_bytes']>512*2**20),'RESOURCE_SWAP_GROWTH'
 return row
def dispatch(ident,**extra):
 guard();n=sum(r['event']=='START' for r in events());limit=300 if MODE.startswith('V') or MODE=='verify' else 252
 assert n<limit,'RESERVED_VALIDATION_OR_TOTAL_CAP';assert time.time()<P['dispatch_cutoff_unix']-600,'INSUFFICIENT_CLOSEOUT_TIME';assert not any(r['event']=='START' and r['id']==ident for r in events()),'DUPLICATE_ATTEMPT'
 if n%5==0:resource_check()
 mh.event('START',ident,mode=MODE,**extra)
 put('PROGRESS.json',dict(unix=time.time(),phase=MODE,current_attempt=ident,attempts=n+1,status='RUNNING',hard_stop_unix=P['hard_stop_unix']))
mh.dispatch=dispatch;sd.dispatch=dispatch
def normalized_constraints(m,b,c):
 pr=json.loads((S/'MOTION_ACCEPTANCE_PROTOCOL.json').read_text())['primary'];v={k:np.asarray(r)/pr['burden_ratio'] for k,r in c['burden_ratios'].items()}
 v.update(excursion=np.asarray(c['excursion_delta_deg'])/.5,cumulative_upper=np.asarray(c['cumulative_ratio'])/1.05,cumulative_lower=.95/np.asarray(c['cumulative_ratio']),endpoint=np.asarray(c['endpoint_abs_delta_deg'])/.5,boundary=c['phase_boundary_max_delta_deg']/.5,duration=c['duration_abs_delta_s']/.1,moment_integral=m['moment_integral_Nm_s']/(b['moment_integral_Nm_s']*1.25),force_peak=m['force_peak_N']/(b['force_peak_N']*1.05),moment_peak=m['moment_peak_Nm']/(b['moment_peak_Nm']*1.05),tracking=np.asarray(m['tracking_RMS_deg'])/(np.asarray(b['tracking_RMS_deg'])+.5))
 for ph in ['OUTBOUND','HOLD','RETURN']:v[ph+'_duration']=abs(m['phase_durations'][ph]-b['phase_durations'][ph])/.1
 worst=max((float(np.max(x)),k) for k,x in v.items());return dict(components=v,worst_ratio=worst[0],worst_requirement=worst[1],positive_violation_sum=sum(float(np.maximum(np.asarray(x)-1,0).sum()) for x in v.values()),search_guidance_only=True,acceptance_unchanged=True)
def actual_signature(ident):
 rows=json.loads((S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')).read_text())['rows']
 return [(r['phase'],r['decision_index'],r['native_coordination_metadata'],r['first_execution_physics_s'],r['actual_native_steps']) for r in rows if r['physically_executed_nonzero']]
def summarize(ident,base,cand):
 row=sd.summarize(ident,base,cand);m=sd.metric(ident);c=row['comparison'];row['continuous_constraints']=normalized_constraints(m,base,c)
 refpath=S/'reports'/(ident.split('_')[0]+'_C4_1_5_MEASURED.json')
 if not refpath.exists() and not MODE.startswith('V'):refpath=S/'reports/baseline_C4_1_5_MEASURED.json'
 if refpath.exists():
  ref=json.loads(refpath.read_text());row['extra_gain_vs_C4_N_s']=ref['J_F_N_s']-m['J_F_N_s'];row['extra_gain_vs_C4_percent']=100*row['extra_gain_vs_C4_N_s']/ref['J_F_N_s']
 row['actual_execution_signature']=actual_signature(ident)
 seeds=[r for r in evaluations() if r['id'].startswith('baseline_') and r['candidate_id']==cand.get('parameters',{}).get('source')]
 if seeds:
  seed=seeds[0];g=seed['comparison']['gain_percent'];row['seed_gain_retention_ratio']=c['gain_percent']/g if abs(g)>1e-12 else None;row['worst_constraint_ratio_change_vs_seed']=row['continuous_constraints']['worst_ratio']-seed['continuous_constraints']['worst_ratio']
 append('EVALUATIONS.jsonl',row);append('REPAIR_LINEAGE.jsonl',dict(id=ident,candidate=cand,parent=m['branch'],source=cand.get('parameters',{}).get('source'),modification=cand.get('parameters',{}),result=row))
 data=json.loads((S/'output'/(ident+'_DATA.json')).read_text());dec=json.loads((S/'output'/(ident+'_DECISIONS.json')).read_text())['rows']
 append('TEACHER_COMPACT.jsonl',dict(id=ident,condition=data['condition'],parent=data['branch_start'],candidate=cand,kind='full_task_policy_and_fork_suffix',continuation=P['continuation'] if cand['id']!='Frozen_M2' else 'frozen historical Q rolling reselection; original B physical segment continuation',full_J_F_N_s=m['J_F_N_s'],remaining_J_F_N_s=data['remaining_J_F'],current_inputs=[{k:d.get(k) for k in ['phase','start_m','nominal_m','nominal_d','nominal_target','observation','task_s','model_hash','richer_previous_residual','native_index','legal_shared_prefix']} for d in dec],action_encoding=[{k:d.get(k) for k in ['phase','native_index','graph','registered_spec','action','raw_v2']} for d in dec],future_audit_label_reference=m['execution_lineage_path'],motion_label=m['motion']['raw']['full'],task_complete=True,no_future_audit_in_inputs=True))
 return row
def catalog():return {c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
def evaluations():return [json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()] if (S/'EVALUATIONS.jsonl').exists() else []
class Worker(sd.SearchInterface):
 def __init__(self,condition):
  super().__init__(condition,False);self.executed=set();self.family_fail={};self.results=[]
  if MODE.startswith(('mechanism','repair','reexplore')):
   for r in evaluations():
    if r['id'].startswith(('V','verify')):continue
    old=self.lookup.get(r['candidate_id'])
    if old:self.executed.add(digest({k:old.get(k) for k in ['phases','table']}))
 def store_catalog(self):put('CANDIDATE_CATALOG.json',dict(candidates=list(self.lookup.values()),updated_unix=time.time()))
 def fork(self,b,tag,table=None):
  answer=super().fork(b,tag,table)
  if answer:
   signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_CHILD_600S_TIMEOUT')));signal.alarm(600)
  return answer
 def attempt(self,b,cand):
  key=digest({k:cand.get(k) for k in ['phases','table']})
  if key in self.executed:append('SKIPPED_DUPLICATES.jsonl',dict(candidate=cand['id'],reason='identical registered graph/table in same parent contract'));return False
  family=cand.get('parameters',{}).get('source',cand['id'])
  if self.family_fail.get(family,0)>=3:return False
  self.executed.add(key);self.lookup[cand['id']]=cand;self.store_catalog()
  try:
   if self.fork(b,cand['id'],np.asarray(cand.get('table',ZERO))):return True
  except AssertionError as e:
   if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
   sd.classify_task_failure(self.condition['name']+'_'+cand['id'],cand);self.family_fail[family]=self.family_fail.get(family,0)+1;return False
  row=summarize(self.condition['name']+'_'+cand['id'],self.base,cand);self.results.append(row);self.family_fail[family]=0;return False
 def decision_boundary(self,b):
  ph=b['task_state'].phase.value
  if self.child is None and not self.fork_done and ph=='OUTBOUND' and self.count['OUTBOUND']>=len(self.condition.get('prefix',{}).get('OUTBOUND',[])):
   self.fork_done=True
   for tag in ['B0_repeat_1','B0_repeat_2'] if MODE=='baseline' else ['B0_repeat_1']:
    if self.fork(b,tag,ZERO):return self.control(b)
   group=self.condition['name'];self.base=sd.metric(group+'_B0_repeat_1')
   if MODE=='baseline':
    gate=mh.complete_gate(group+'_B0_repeat_1',group+'_B0_repeat_2');put('ZERO_FORK_GATE.json',gate);assert gate['status']=='PASS','ZERO_FORK_GATE_FAILED'
   else:
    if not MODE.startswith('V'):
     gate=mh.complete_gate(group+'_B0_repeat_1','baseline_B0_repeat_1');put(MODE+'_PARENT_REBUILD_GATE.json',gate);assert gate['status']=='PASS','PARENT_REBUILD_MISMATCH'
   if MODE=='baseline':
    for c in self.lookup.values():
     if self.attempt(b,c):return self.control(b)
    if self.fork(b,'Frozen_M2'):return self.control(b)
    summarize(group+'_Frozen_M2',self.base,dict(id='Frozen_M2',stage='REFERENCE',parameters={'frozen_Q':True}))
    c=copy.deepcopy(self.lookup['C4_1_5']);c['id']='C4_repeat'
    if self.fork(b,c['id'],ZERO):return self.control(b)
    # Repeat bypasses duplicate filter deliberately, only numerical reproducibility.
    self.lookup[c['id']]=c
   elif MODE.startswith(('mechanism','repair','reexplore')):
    for cand in json.loads((S/'queue'/(MODE+'.json')).read_text())['candidates']:
     if time.time()>=P['dispatch_cutoff_unix']-900:break
     if self.attempt(b,cand):return self.control(b)
   elif MODE.startswith('V'):
    frozen=json.loads((S/'FROZEN_SELECTION.json').read_text())
    for cand in [self.lookup['C4_1_5']]+frozen['candidates']:
     if self.attempt(b,cand):return self.control(b)
   elif MODE=='verify':
    frozen=json.loads((S/'FROZEN_SELECTION.json').read_text())
    if frozen['candidates']:
     cand=copy.deepcopy(frozen['candidates'][0]);cand['id']='new_repeat_1'
     if self.attempt(b,cand):return self.control(b)
     cand=copy.deepcopy(cand);cand['id']='new_repeat_2';self.lookup[cand['id']]=cand
     if self.fork(b,cand['id'],np.asarray(cand.get('table',ZERO))):return self.control(b)
     summarize(group+'_'+cand['id'],self.base,cand)
     gate=mh.complete_gate(group+'_new_repeat_1',group+'_new_repeat_2');put('NEW_CANDIDATE_REPEAT_GATE.json',gate);assert gate['status']=='PASS'
  self.control(b)
def main():
 condition=next(c for c in P['validation_conditions'] if c['name']==MODE) if MODE.startswith('V') else dict(name=MODE,seed=P['seed'],prefix={})
 ident=condition['name']+'_parent_B0';dispatch(ident,kind='COLD_START_PARENT_FULL_TASK',condition=condition)
 random.seed(condition['seed']);np.random.seed(condition['seed']);interface=Worker(condition)
 # Child lookup must already contain numerical repeat spec at fork.
 if MODE=='baseline':
  c=copy.deepcopy(interface.lookup['C4_1_5']);c['id']='C4_repeat';interface.lookup[c['id']]=c
 try:
  m=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'],'PARENT_TASK_INVALID'
  base=sd.metric(ident);gate=mh.complete_gate(ident,condition['name']+'_B0_repeat_1');put(MODE+'_PARENT_CHILD_GATE.json',gate);assert gate['status']=='PASS'
  if MODE=='baseline':
   gate=mh.complete_gate('baseline_C4_1_5','baseline_C4_repeat');put('C4_REPEAT_GATE.json',gate);assert gate['status']=='PASS'
   gate=mh.complete_gate('baseline_M2_fixed_actions','baseline_Frozen_M2');put('M2_FIXED_VS_ROLLING_GATE.json',gate)
   neg=am.negcontrol('baseline_C4_1_5','baseline_B0_repeat_1');put('RETURN_NEGATIVE_CONTROL.json',neg);assert neg['all_pre_intervention_fields_exact_equal'],'RETURN_PREFIX_MISMATCH'
  if MODE=='verify':
   frozen=json.loads((S/'FROZEN_SELECTION.json').read_text())
   if frozen['candidates'] and set(frozen['candidates'][0].get('phases',{}))=={'RETURN'}:
    neg=am.negcontrol('verify_new_repeat_1','verify_B0_repeat_1');put('NEW_RETURN_NEGATIVE_CONTROL.json',neg);assert neg['all_pre_intervention_fields_exact_equal']
  resource_check();put(MODE+'_DONE.json',dict(unix=time.time(),status='COMPLETE',attempts=sum(r['event']=='START' for r in events()),owned_children_joined=True))
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  mh.event('FAIL',ident,error=str(e),joined=True);put('PHYSICS_STOP.json',dict(unix=time.time(),mode=MODE,reason=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
