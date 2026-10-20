from study_common import *
import matched_harness as mh
import analyze_matched as am
import random,traceback,copy,subprocess,signal,resource
S=STUDY
P=json.loads((S/'SEARCH_PROTOCOL.json').read_text())
CAT=json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']
ZERO=np.zeros((2,5,3))
def put(name,x):mh.put(S/name,x)
def resources():
 mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()}
 disk=shutil.disk_usage('/mnt/d');size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())
 usage=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
 row=dict(unix=time.time(),pid=os.getpid(),linux_available_bytes=mem['MemAvailable'],linux_swap_free_bytes=mem['SwapFree'],D_free_bytes=disk.free,study_bytes=size,self_cpu_s=usage.ru_utime+usage.ru_stime,joined_children_cpu_s=children.ru_utime+children.ru_stime,self_max_rss_KiB=usage.ru_maxrss,children_max_rss_KiB=children.ru_maxrss)
 with (S/'RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 assert mem['MemAvailable']>=2**30,'LOW_MEMORY';assert disk.free>=20*2**30,'LOW_D_SPACE';assert size<12*2**30,'STORAGE_CAP'
 return row
def dispatch(ident,**extra):
 guard();n=sum(r['event']=='START' for r in mh.records());assert n<160,'ATTEMPT_CAP';assert not any(r['event']=='START' and r['id']==ident for r in mh.records()),'NO_REPEAT'
 if n%5==0:resources()
 mh.event('START',ident,**extra)
mh.dispatch=dispatch
def metric(ident):
 path=S/'reports'/(ident+'_MEASURED.json')
 return json.loads(path.read_text()) if path.exists() else am.measure(ident)
def summarize(ident,base,candidate):
 m=metric(ident);comparison=am.compare(m,base);line=json.loads((S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')).read_text())
 data=json.loads((S/'output'/(ident+'_DATA.json')).read_text());fork_s=(data.get('child') or {}).get('physical_time_at_fork',0.)
 owned_new=[r for r in line['rows'] if r['physically_executed_nonzero'] and r['first_execution_physics_s']>=fork_s-1e-9]
 executed={r['phase'] for r in owned_new}
 target=set(candidate.get('phases',{})) if 'phases' in candidate else {ph for ph,i in [('OUTBOUND',0),('RETURN',1)] if np.any(np.asarray(candidate.get('table',ZERO))[i])}
 comparison.update(actual_nonzero_count=len(owned_new),actual_nonzero_native_steps=sum(r['actual_native_steps'] for r in owned_new),inherited_nonzero_plan_count=line['actual_nonzero_count']-len(owned_new),executed_phases=sorted(executed),eligible=bool(comparison['acceptance_pass'] and comparison['gain_percent']>=.5 and target.issubset(executed) and bool(target)))
 result=dict(id=ident,candidate_id=candidate['id'],stage=candidate.get('stage','VALIDATION'),parameters=candidate.get('parameters',{}),comparison=comparison,metrics_path=str(S/'reports'/(ident+'_MEASURED.json')),runtime_lineage_path=m['execution_lineage_path'],actual_new_native_steps=m['actual_new_native_steps'])
 with (S/'RESULTS.jsonl').open('a') as f:f.write(json.dumps(clean(result),allow_nan=False)+'\n')
 print(json.dumps(dict(progress=ident,J_F=m['J_F_N_s'],gain_percent=comparison['gain_percent'],motion=comparison['acceptance_pass'],failed=comparison['failed_requirements'],executed=line['actual_nonzero_count'],attempts=sum(r['event']=='START' for r in mh.records()))),flush=True)
 return result
class SearchInterface(mh.MatchedInterface):
 def __init__(self,condition,validation=False):
  super().__init__(condition,validation);self.lookup={r['id']:r for r in CAT};self.results=[];self.base=None;self.stop_reason=None;self.consecutive_failed=0
  if condition.get('resume'):
   self.results=[json.loads(r) for r in (S/'RESULTS.jsonl').read_text().splitlines() if json.loads(r)['id'].startswith('discovery_')]
   self.consecutive_failed=1
 def manifest(self,b):
  m=super().manifest(b)
  # Candidate is assigned only after fork; parent always has empty residual state.
  return m
 def control(self,b):
  # Held-out forks occur after the shared prefix. The frozen M2 coordinator
  # must continue the inherited issued-slot/history state, not issue it again.
  if self.policy is not None and not getattr(self.policy,'shared_prefix_synced',False):
   self.policy.count=self.count.copy();self.policy.previous=self.previous.copy();self.policy.model_hash=self.model_hash
   self.policy.labels=copy.deepcopy(self.labels);self.policy.skips=copy.deepcopy(self.skips);self.policy.shared_prefix_synced=True
  return super().control(b)
 def choose(self,b,c):
  if self.child is None:return super().choose(b,c)
  tag=self.child['kind'];candidate=self.lookup.get(tag)
  if not candidate:return super().choose(b,c)
  if 'table' in candidate:
   self.table=np.asarray(candidate['table']);return super().choose(b,c)
  ph=c['phase'];i=self.count[ph];self.count[ph]+=1
  spec=candidate.get('phases',{}).get(ph,[None]*5)[i] if i<5 else None
  if spec is None:self.apply(b,c,np.zeros(3),np.zeros(3));self.labels[-1].update(native_index=i,search_candidate=tag);return
  assert max(abs(np.asarray(spec['values'])))<=.2+1e-12
  start=c['start_m'];lo,hi=spec['support'];fraction=np.r_[lo,lo+(hi-lo)*np.asarray(spec['knots']),hi]
  knots=start+(1-start)*fraction;values=np.r_[0.,spec['values'],0.];pairs=np.column_stack([knots,values]).tolist()
  if pairs[0][0]>0:pairs=[[0.,0.]]+pairs
  if pairs[-1][0]<1:pairs=pairs+[[1.,0.]]
  a=np.asarray(pairs);assert a[0].tolist()==[0.,0.] and a[-1].tolist()==[1.,0.] and np.all(np.diff(a[:,0])>0)
  self.action={ph:pairs};b['planner'].residual_spec=self.action
  self.labels.append(dict(**c,action=[0.,0.,0.],teacher_label=[0.,0.,0.],graph=self.action,expected_delta=float(np.interp(c['nominal_m'],a[:,0],a[:,1])),native_index=i,search_candidate=tag,raw_v2=True,registered_spec=spec));self.previous=np.zeros(3)
 def attempt(self,b,candidate):
  tag=candidate['id'];self.lookup[tag]=candidate
  # Never repeat a completed or failed candidate during recovery.
  if any(r['event']=='START' and r['id'].endswith('_'+tag) and r['id'].startswith('discovery_') for r in mh.records()):return False
  try:
   if self.fork(b,tag,np.asarray(candidate.get('table',ZERO))):return True
  except AssertionError as e:
   if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
   ident=self.condition['name']+'_'+tag;failed=classify_task_failure(ident,candidate)
   self.consecutive_failed+=1;print(json.dumps(dict(progress=ident,status='TASK_INVALID_UNRANKED',reason=failed['abort_reason'],attempts=sum(r['event']=='START' for r in mh.records()))),flush=True)
   if self.consecutive_failed>=3:self.stop_reason='THREE_CONSECUTIVE_FAILED_ATTEMPTS'
   return False
  ident=self.condition['name']+'_'+tag;row=summarize(ident,self.base,candidate);self.results.append(row)
  self.consecutive_failed=0
  return False
 def store_catalog(self):
  put('CANDIDATE_CATALOG.json',dict(frozen_initial_protocol=True,candidates=list(self.lookup.values()),adaptive_rule=P['C2_adaptive_rule'],local_rule=P['C4_rule'],updated_unix=time.time()))
 def ranked(self,ph):
  rows=[r for r in self.results if r['stage']=='C1' and self.lookup[r['candidate_id']]['parameters']['phase']==ph]
  return sorted(rows,key=lambda r:(not r['comparison']['acceptance_pass'],-r['comparison']['gain_percent'],r['candidate_id']))
 def discovery(self,b):
  for tag in ['B0_repeat_1','B0_repeat_2']:
   if self.fork(b,tag,ZERO):return True
  group=self.condition['name'];gate=mh.complete_gate(group+'_B0_repeat_1',group+'_B0_repeat_2');put('OUTBOUND_FORK_GATE'+('_RECOVERY' if self.condition.get('resume') else '')+'.json',gate);assert gate['status']=='PASS','FORK_GATE_FAILED'
  self.base=metric(group+'_B0_repeat_1')
  if self.condition.get('resume'):
   cross=mh.complete_gate(group+'_B0_repeat_1','discovery_B0_repeat_1');put('FRESH_PARENT_COMPARABILITY_GATE.json',cross);assert cross['status']=='PASS','FRESH_PARENT_COMPARABILITY_FAIL'
  else:
   if self.fork(b,'Frozen_M2'):return True
   summarize(group+'_Frozen_M2',self.base,dict(id='Frozen_M2',stage='REFERENCE',table=np.ones((2,5,3)).tolist(),parameters={'frozen_Q':True}))
  for stage in ['C1','REFERENCE','C2','C3']:
   rows=[r for r in CAT if r['stage']==stage]
   if stage=='C2':
    os_=self.ranked('OUTBOUND')[:3];rs=self.ranked('RETURN')[:4]
    for oi,o in enumerate(os_):
     for ri,r in enumerate(rs):
      oc=self.lookup[o['candidate_id']];rc=self.lookup[r['candidate_id']]
      cand=dict(id=f'C2_pair_{oi}_{ri}',stage='C2',phases={**oc['phases'],**rc['phases']},parameters={'O_source':oc['id'],'R_source':rc['id']})
      self.lookup[cand['id']]=cand;rows.append(cand)
    self.store_catalog()
   for cand in rows:
    if self.stop_reason:return False
    if time.time()>=P['dispatch_cutoff_unix']-120:self.stop_reason='DISPATCH_CUTOFF';return False
    if self.attempt(b,cand):return True
  regions=[]
  ranked=sorted(self.results,key=lambda r:(not r['comparison']['acceptance_pass'],0 if r['comparison']['acceptance_pass'] else max(max(v) for v in r['comparison']['burden_ratios'].values()),-r['comparison']['gain_percent'],r['candidate_id']))
  used=set()
  for r in ranked:
   c=self.lookup[r['candidate_id']]
   if c['stage']=='REFERENCE':continue
   key=(c['stage'],tuple(sorted(c.get('phases',{}))))
   if key not in used:regions.append(c);used.add(key)
   if len(regions)==3:break
  for i,c in enumerate(regions):
   for j,factor in enumerate([.6,.8,.9,1.1,1.2,1.4,-.5,-1.]):
    cand=copy.deepcopy(c);cand.update(id=f'C4_{i}_{j}',stage='C4',parameters={'region_source':c['id'],'factor':factor})
    for specs in cand['phases'].values():
     for sp in specs:
      if sp is not None:sp['values']=np.clip(np.asarray(sp['values'])*factor,-.2,.2).tolist();sp['amplitude']=float(np.clip(sp['amplitude']*factor,-.2,.2))
    self.lookup[cand['id']]=cand;self.store_catalog()
    if self.stop_reason:return False
    if time.time()>=P['dispatch_cutoff_unix']-120:self.stop_reason='DISPATCH_CUTOFF';return False
    if self.attempt(b,cand):return True
  return False
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value
  if self.child is None and not self.fork_done and phase=='OUTBOUND' and self.count['OUTBOUND']>=len(self.condition.get('prefix',{}).get('OUTBOUND',[])):
   self.fork_done=True
   if self.validation:
    sel=json.loads((S/'FROZEN_SELECTION.json').read_text())
    for cand in sel['candidates']:
     self.lookup[cand['id']]=cand
     try:
      if self.fork(b,cand['id'],np.asarray(cand.get('table',ZERO))):return self.control(b)
     except AssertionError as e:
      if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
      classify_task_failure(self.condition['name']+'_'+cand['id'],{**cand,'stage':'VALIDATION'})
    try:
     if self.fork(b,'Frozen_M2'):return self.control(b)
    except AssertionError as e:
     if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
     classify_task_failure(self.condition['name']+'_Frozen_M2',dict(id='Frozen_M2',stage='VALIDATION_REFERENCE',parameters={}))
   elif self.discovery(b):return self.control(b)
  if self.child is None and not self.validation and not self.return_fork_done and phase=='RETURN' and not self.stop_reason and time.time()<P['dispatch_cutoff_unix']-120:
   self.return_fork_done=True;self.quiescent_ready=False
   for tag in ['RETURN_entry_zero','RETURN_entry_repeat']:
    if self.fork(b,tag,ZERO):return self.control(b)
   group=self.condition['name'];gate=mh.complete_gate(group+'_RETURN_entry_zero',group+'_RETURN_entry_repeat');put('RETURN_FORK_GATE.json',gate);assert gate['status']=='PASS'
   leaders=self.ranked('RETURN')
   if leaders and time.time()<P['dispatch_cutoff_unix']-120:
    best=copy.deepcopy(self.lookup[leaders[0]['candidate_id']]);best.update(id='RETURN_entry_R_best',stage='RETURN_DIAGNOSTIC',parameters={'source':leaders[0]['candidate_id']});self.lookup[best['id']]=best;self.store_catalog()
    if self.fork(b,best['id'],ZERO):return self.control(b)
    summarize(group+'_'+best['id'],metric(group+'_RETURN_entry_zero'),best)
  self.control(b)
def select():
 rows=[json.loads(r) for r in (S/'RESULTS.jsonl').read_text().splitlines()];valid=[r for r in rows if r['comparison']['eligible'] and r['candidate_id']!='Frozen_M2'];catalog=json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates'];lookup={r['id']:r for r in catalog};chosen=[]
 if valid:
  ordered=sorted(valid,key=lambda r:(-r['comparison']['gain_percent'],r['candidate_id']));chosen.append(ordered[0])
  smooth=min(valid,key=lambda r:(max(max(v) for v in r['comparison']['burden_ratios'].values()),-r['comparison']['gain_percent'],r['candidate_id']))
  if smooth not in chosen:chosen.append(smooth)
  for r in ordered:
   if r not in chosen and lookup[r['candidate_id']].get('parameters',{}).get('phase')!=lookup[chosen[0]['candidate_id']].get('parameters',{}).get('phase'):chosen.append(r);break
 selected=dict(unix=time.time(),status='DISCOVERY_PASS_PENDING_VALIDATION' if chosen else 'NOT_RUN_DISCOVERY_GATE_FAILED',candidates=[lookup[r['candidate_id']] for r in chosen[:3]],discovery_rows=chosen[:3],eligible_count=len(valid),no_holdout_used=True,protocol_sha256=sha(S/'SEARCH_PROTOCOL.json'))
 put('FROZEN_SELECTION.json',selected);return selected
def classify_task_failure(ident,candidate):
 data=json.loads((S/'output'/(ident+'_DATA.json')).read_text());m=data['metric'];audit=m['physical_audit'];ev=audit['unchanged_evaluator'];phys=ev['physical_task_result'];conditions=phys['scorer_v2_common_conditions']
 hard=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation','case_hash']
 safety=all(conditions.get(k) is True for k in hard) and phys.get('finite_trace') and phys.get('finite_native') and phys.get('activation_certificates_valid') and phys.get('reference_boundary_C2')
 from stream_runtime_evidence import array_items
 directory=S/'source/results'/ident;summary=json.loads((directory/'summary.json').read_text());native=list(array_items(directory/'runtime_artifacts.json.gz','native_states_evaluation_only'));line=am.lineage(ident,summary,native)
 result=dict(id=ident,candidate_id=candidate['id'],stage=candidate['stage'],parameters=candidate.get('parameters',{}),status='TASK_INVALID_UNRANKED',task_valid=False,motion_accepted='NOT_EVALUABLE_FULL_TASK',full_task_gain='NOT_EVALUABLE',observed_partial_J_F=m['J_F'],observed_native_steps=m['actual_new_native_physics_steps'],abort_reason=ev['raw_scorer_v2'].get('abort_reason'),native_absolute_safety_pass=bool(safety),hard_conditions={k:conditions.get(k) for k in hard},actual_write_ownership=line['status'],actual_nonzero_count=line['actual_nonzero_count'],original_scientific_validity=ev['scientific_validity'],full_audit_path=str(directory/'SAC_PHYSICAL_AUDIT.json'),why_unranked='missing complete OUTBOUND/HOLD/RETURN; partial integral cannot compete with full-task B')
 put('reports/'+ident+'_TASK_FAILURE.json',result);mh.event('TASK_INVALID',ident,reason=result['abort_reason'],native_absolute_safety_pass=bool(safety),actual_write_ownership=line['status'])
 assert safety,'NATIVE_ABSOLUTE_SAFETY_FAILURE';assert line['status']=='PASS','NATIVE_OWNERSHIP_FAILURE'
 return result
def main():
 mode=sys.argv[1] if len(sys.argv)>1 else 'discovery'
 discovery_mode=mode in ['discovery','resume']
 condition=dict(name='discovery_resume' if mode=='resume' else 'discovery',seed=P['seed'],prefix={},resume=mode=='resume') if discovery_mode else next(c for c in P['validation_conditions'] if c['name']==mode)
 ident=condition['name']+'_parent_B0';dispatch(ident,kind='COLD_START_PARENT_FULL_TASK',condition=condition,clock='SCIENTIFIC_MATCHED_EXECUTION')
 put('WORKER_'+mode+'.json',dict(pid=os.getpid(),unix=time.time(),condition=condition,status='RUNNING'))
 random.seed(condition['seed']);np.random.seed(condition['seed']);interface=SearchInterface(condition,not discovery_mode)
 try:
  m=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid']
  base=metric(ident)
  if discovery_mode:
   parentgate=mh.complete_gate(condition['name']+'_parent_B0',condition['name']+'_B0_repeat_1');put('PARENT_VS_CHILD_GATE.json',parentgate);assert parentgate['status']=='PASS'
   put('DISCOVERY_STOP.json',dict(unix=time.time(),reason=interface.stop_reason or 'REGISTERED_SEARCH_COMPLETE',attempts=sum(r['event']=='START' for r in mh.records())));select()
  else:
   selected=json.loads((S/'FROZEN_SELECTION.json').read_text())
   for c in selected['candidates']:
    child_id=condition['name']+'_'+c['id']
    if not (S/'reports'/(child_id+'_TASK_FAILURE.json')).exists():summarize(child_id,base,c)
   child_id=condition['name']+'_Frozen_M2'
   if not (S/'reports'/(child_id+'_TASK_FAILURE.json')).exists():summarize(child_id,base,dict(id='Frozen_M2',stage='VALIDATION_REFERENCE',table=np.ones((2,5,3)).tolist()))
  resources();put('WORKER_'+mode+'.json',dict(pid=os.getpid(),unix=time.time(),condition=condition,status='EXITING_SUCCESS'));print('PARENT_COMPLETE '+ident,flush=True)
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  mh.event('END',ident,returncode=1,joined=True,error=str(e));raise
if __name__=='__main__':main()
