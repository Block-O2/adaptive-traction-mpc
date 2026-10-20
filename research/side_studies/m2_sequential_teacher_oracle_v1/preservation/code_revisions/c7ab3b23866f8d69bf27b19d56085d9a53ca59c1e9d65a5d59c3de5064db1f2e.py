from study_common import *
import matched_harness as mh, analyze_matched as am, search_driver as sd
import copy,random,signal,traceback,fcntl
S=STUDY;P=json.loads((S/'SEARCH_PROTOCOL.json').read_text());ZERO=np.zeros((2,5,3))
MODE=sys.argv[1];Q=json.loads((S/'queue'/(MODE+'.json')).read_text())
def put(n,x):mh.put(S/n,x)
def append(n,x):
 with (S/n).open('a') as f:f.write(json.dumps(clean(x),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def resources():
 mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()};disk=shutil.disk_usage('/mnt/d');size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())
 row=dict(unix=time.time(),D_free_bytes=disk.free,package_bytes=size,linux_available_bytes=mem['MemAvailable'],swap_used_bytes=mem['SwapTotal']-mem['SwapFree']);append('RESOURCE_SAMPLES.jsonl',row)
 assert disk.free>=40*2**30 and size<6*2**30 and mem['MemAvailable']>=2**30,'RESOURCE_STOP'
def dispatch(ident,**extra):
 guard();n=sum(r['event']=='START' for r in mh.records());assert n<(90 if MODE.startswith(('V','verify')) else 72),'ATTEMPT_RESERVATION';assert time.time()<P['dispatch_cutoff_unix']-(180 if MODE.startswith(('V','verify')) else 420),'CLOSEOUT_RESERVE'
 if not MODE.startswith(('V','verify')):assert time.time()<P['search_cutoff_unix'],'SEARCH_CUTOFF'
 assert not any(r['event']=='START' and r['id']==ident for r in mh.records()),'DUPLICATE_START'
 resources();mh.event('START',ident,mode=MODE,**extra);put('PROGRESS.json',dict(mode=MODE,id=ident,attempts=n+1,unix=time.time()))
mh.dispatch=dispatch;sd.dispatch=dispatch
def worst(m,b,c):
 v={k:np.asarray(r)/1.1 for k,r in c['burden_ratios'].items()};v.update(excursion=np.asarray(c['excursion_delta_deg'])/.5,cumulative_upper=np.asarray(c['cumulative_ratio'])/1.05,cumulative_lower=.95/np.asarray(c['cumulative_ratio']),boundary=c['phase_boundary_max_delta_deg']/.5,endpoint=np.asarray(c['endpoint_abs_delta_deg'])/.5,duration=c['duration_abs_delta_s']/.1,moment=m['moment_integral_Nm_s']/(b['moment_integral_Nm_s']*1.25),tracking=np.asarray(m['tracking_RMS_deg'])/(np.asarray(b['tracking_RMS_deg'])+.5),force_peak=m['force_peak_N']/(b['force_peak_N']*1.05),moment_peak=m['moment_peak_Nm']/(b['moment_peak_Nm']*1.05))
 w=max((float(np.max(x)),k) for k,x in v.items());return dict(worst_ratio=w[0],worst_requirement=w[1],components=v)
def summarize(ident,base,cand):
 r=sd.summarize(ident,base,cand);m=sd.metric(ident);r['continuous_constraints']=worst(m,base,r['comparison']);r['J_F_N_s']=m['J_F_N_s'];r['phase_J_F_N_s']={p:x['J_F_N_s'] for p,x in m['phase_cost']['phases'].items()}
 line=json.loads((S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')).read_text());r['actual_execution']=[{k:d.get(k) for k in ['phase','decision_index','native_coordination_metadata','physically_executed_nonzero','first_execution_physics_s','actual_native_steps']} for d in line['rows']]
 full_phases={d['phase'] for d in line['rows'] if d['physically_executed_nonzero']};target={ph for ph,ss in cand.get('phases',{}).items() if any(ss)}
 r['comparison']['full_task_executed_phases']=sorted(full_phases);r['comparison']['eligible']=bool(r['comparison']['acceptance_pass'] and r['comparison']['gain_percent']>=.5 and target and target.issubset(full_phases))
 r['eligibility_scope']='complete executed policy, including lawful inherited ancestor; suffix-owned counts kept separately'
 r['candidate']=cand;r['parent_prefix']=Q.get('parent_candidate');r['fork_boundary']=Q.get('boundary',['OUTBOUND',0]);r['offline_future_evaluation']=True
 append('EVALUATIONS.jsonl',r)
 decisions=json.loads((S/'output'/(ident+'_DECISIONS.json')).read_text())['rows'];data=json.loads((S/'output'/(ident+'_DATA.json')).read_text())
 append('TEACHER_DATA.jsonl',dict(id=ident,condition=data['condition'],state=data['branch_start'],prefix_actions=[d for d in decisions if d.get('current_inputs') is not None],candidate=cand,full_J_F_N_s=m['J_F_N_s'],remaining_J_F_N_s=data['remaining_J_F'],motion_pass=r['comparison']['acceptance_pass'],future_labels_separate=True,raw_v2_zero_is_placeholder=True))
 return r
def ancestor_gate(a,b):
 if (O/b/'runtime_artifacts.json.gz').exists():return mh.complete_gate(a,b)
 # Ordinary ancestors may have been compacted after their full ownership audit.
 # Dense native human state and all archived control trace fields remain.
 errors=[]
 for pa,pb in [(O/a/'trace.npz',O/b/'trace.npz'),(S/'motion_series'/(a+'.npz'),S/'motion_series'/(b+'.npz'))]:
  with np.load(pa) as x,np.load(pb) as y:
   assert set(x.files)==set(y.files)
   for k in x.files:
    same=x[k].shape==y[k].shape and (np.array_equal(x[k],y[k],equal_nan=True) if x[k].dtype.kind in 'fc' else np.array_equal(x[k],y[k]))
    if not same:errors.append(dict(file=pa.name,field=k))
 ma=sd.metric(a);mb=sd.metric(b)
 for k in ['J_F_N_s','moment_integral_Nm_s','native_steps']:
  if ma[k]!=mb[k]:errors.append(dict(metric=k,a=ma[k],b=mb[k]))
 return dict(status='PASS' if not errors else 'FAIL',scope='exact archived control trace and dense native human q/dq/derivatives; integrals and total steps; both original full receipt ownership audits PASS',old_raw_compacted=True,direct_full_receipt_and_other_native_body_repeat='NOT_EVALUABLE',errors=errors,branches=[a,b])
class Sequential(sd.SearchInterface):
 def __init__(self,condition):
  super().__init__(condition,False);self.lookup.update({c['id']:c for c in Q['candidates']});self.parent_candidate=Q.get('parent_candidate',dict(id='B0',phases={}));self.lookup[self.parent_candidate['id']]=self.parent_candidate
  self.base=None;self.stopped_families=set();self.failed={}
 def choose(self,b,c):
  current=dict(observation=c['observation'],model_beta=b['belief'].beta,model_residual=b['belief'].state_residual_weights_nm,phase=c['phase'],task_s=c['task_s'],physical_time_s=float(b['physical_now']),reference_state=b['arguments']['current_reference_state'],reference_acceleration=b['reference_acceleration'],issued_count=self.count.copy(),previous_registered_graph=copy.deepcopy(self.action),issued_history=[{k:d.get(k) for k in ['phase','native_index','graph','registered_spec','action']} for d in self.labels])
  prior=self.child
  if prior is None:self.child={'kind':self.parent_candidate['id']}
  try:super().choose(b,c)
  finally:self.child=prior
  if self.labels:self.labels[-1]['current_inputs']=clean(current)
 def fork(self,b,tag,table=None):
  answer=super().fork(b,tag,table)
  if answer:
   limit=180 if MODE.startswith(('V','verify')) else 420;signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_CHILD_WALL_LIMIT')));signal.alarm(limit)
  return answer
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value;boundary=Q.get('boundary',['OUTBOUND',0])
  if self.child is None and not self.fork_done and phase==boundary[0] and self.count.get(phase,0)>=boundary[1]:
   self.fork_done=True
   for cand in Q['candidates']:
    if time.time()>=P['dispatch_cutoff_unix']-(180 if MODE.startswith(('V','verify')) else 420):break
    if not MODE.startswith(('V','verify')) and (time.time()>=P['search_cutoff_unix']-420 or sum(r['event']=='START' for r in mh.records())>=72):break
    family=cand.get('parameters',{}).get('family',cand['id'])
    if family in self.stopped_families:continue
    # A later fork must retain every action already physically issued by its parent.
    for ph in ['OUTBOUND','RETURN']:
     for i in range(self.count[ph]):
      if i<len(self.condition.get('prefix',{}).get(ph,[])):continue
      assert cand.get('phases',{}).get(ph,[None]*5)[i]==self.parent_candidate.get('phases',{}).get(ph,[None]*5)[i],'PREFIX_SEQUENCE_MISMATCH'
    try:
     if self.fork(b,cand['id'],np.asarray(cand.get('table',ZERO))):return self.control(b)
    except AssertionError as e:
     if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
     sd.classify_task_failure(self.condition['name']+'_'+cand['id'],cand);self.failed[family]=self.failed.get(family,0)+1
     if self.failed[family]>=3:self.stopped_families.add(family)
     continue
    ident=self.condition['name']+'_'+cand['id']
    if cand['id'].startswith('B0'):
     m=sd.metric(ident)
     if self.base is None:self.base=m
     if cand['id']=='B0_repeat_2':
      gate=mh.complete_gate(self.condition['name']+'_B0_repeat_1',ident);put('BASELINE_FORK_GATE.json',gate);assert gate['status']=='PASS'
    else:
     base=self.base or sd.metric(Q.get('base_id','baseline_B0_repeat_1'));summarize(ident,base,cand)
   put(MODE+'_FORKS_DONE.json',dict(unix=time.time(),parent_checks=self.parent_checks))
  self.control(b)
def main():
 lock=(S/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 condition=Q.get('condition',dict(name=MODE,seed=P['seed'],prefix={}))
 ident=condition['name']+'_parent';dispatch(ident,kind='LEGAL_COMPLETE_PARENT',condition=condition,parent_candidate=Q.get('parent_candidate'),boundary=Q.get('boundary'))
 random.seed(condition['seed']);np.random.seed(condition['seed']);interface=Sequential(condition)
 try:
  m=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];sd.metric(ident)
  if MODE=='baseline':
   gate=mh.complete_gate(ident,'baseline_B0_repeat_1');put('BASELINE_PARENT_UNPOLLUTED_GATE.json',gate);assert gate['status']=='PASS'
  if Q.get('selected_parent_result'):
   gate=ancestor_gate(ident,Q['selected_parent_result']);put(MODE+'_ANCESTOR_REPLAY_GATE.json',gate);assert gate['status']=='PASS','ANCESTOR_REPLAY_MISMATCH'
  if MODE=='verify':
   gate=mh.complete_gate('verify_best_repeat_1','verify_best_repeat_2');put('BEST_REPEAT_GATE.json',gate);assert gate['status']=='PASS'
  if MODE.startswith('V'):
   gate=mh.complete_gate(ident,condition['name']+'_B0_repeat_1');put(MODE+'_PARENT_B0_GATE.json',gate);assert gate['status']=='PASS'
  if MODE=='baseline_recovery':
   gate=mh.complete_gate(ident,'baseline_B0_repeat_1');put('BASELINE_RECOVERY_PARENT_GATE.json',gate);assert gate['status']=='PASS'
   gate=mh.complete_gate('baseline_recovery_NATIVE_SCALAR_18','baseline_NATIVE_SCALAR_18');put('NATIVE18_REPRODUCTION_GATE.json',gate);assert gate['status']=='PASS'
   gate=mh.complete_gate('baseline_recovery_Frozen_M2','baseline_M2_fixed_actions');put('FROZEN_M2_FIXED_GATE.json',gate)
  put(MODE+'_DONE.json',dict(unix=time.time(),attempts=sum(r['event']=='START' for r in mh.records()),status='COMPLETE',all_children_joined=True));print('COMPLETE '+MODE,flush=True)
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  mh.event('FAIL',ident,error=str(e),joined=True);put('PHYSICS_STOP.json',dict(unix=time.time(),reason=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
