from fork_core import *
class Branches(Interface):
 def __init__(self):
  super().__init__();self.finished=[];self.branch_rows=[];self.branch_output_dir=None
  self.targets=read('BRANCH_CONTRACT.json')['targets']
 def decision_boundary(self,b):
  if self.child is not None:return
  phase=b['task_state'].phase.value
  index=sum(d['phase']==phase for d in b['decisions'])
  candidates=[x for x in self.targets if x['label'] not in self.finished and x['phase']==phase and x['native_index']==index]
  if not candidates:return
  target=candidates[0];label=target['label'];self.finished.append(label)
  quiesce(b);before=state_manifest(b,self);folder=O/'snapshots'/label;folder.mkdir(parents=True,exist_ok=False)
  (folder/'manifest.json').write_text(json.dumps(clean(before),indent=2,sort_keys=True)+'\n')
  for kind,sign in (('baseline',0),('hip',1),('knee',-1)):
   guard();out=O/(label+'_'+kind);out.mkdir(parents=True,exist_ok=False)
   pyrng=random.getstate();nprng=np.random.get_state();pid=os.fork()
   if pid==0:
    random.setstate(pyrng);np.random.set_state(nprng)
    after=state_manifest(b,self)
    if before['hash']!=after['hash']:
     (out/'fork_mismatch_manifest.json').write_text(json.dumps(clean(after),sort_keys=True,indent=2)+'\n');raise RuntimeError('FORK_HASH_MISMATCH')
    env=b['sac_hooks'];belief=b['belief'];model=dict(beta=belief.beta,residual_weights_nm=belief.state_residual_weights_nm,geometry=belief.geometry)
    self.child=dict(label=label,kind=kind,snapshot_hash=before['hash'],start_task_s=float(b['physical_now']-b['task_start_time']),start_J_F=env.force_integral,start_M=env.moment_integral,Human_model_hash=digest(model),human_model_record=clean(model))
    self.branch_output_dir=out;env.episode_dir=out
    m=target['nominal_target_m'];width=read('BRANCH_CONTRACT.json')['graph_half_width'];amp=sign*read('BRANCH_CONTRACT.json')['amplitude']
    self.action={} if sign==0 else {phase:[[0,0],[m-width,0],[m,amp],[m+width,0],[1,0]]}
    b['planner'].residual_spec=self.action
    self.child.update(action=self.action,candidate_progress_horizon=[m-width,m+width],continuation_policy_id='native_B_zero_residual_after_one_spatial_chunk_v2')
    return
   _,status=os.waitpid(pid,0);row=dict(snapshot=label,candidate=kind,exit_code=os.waitstatus_to_exitcode(status))
   if (L/(label+'_'+kind+'_LABEL.json')).exists():row.update(read(label+'_'+kind+'_LABEL.json'))
   self.branch_rows.append(row);save('BRANCH_PROGRESS.json',self.branch_rows)
   if row['exit_code']!=0:raise RuntimeError('BRANCH_CHILD_FAILED:'+label+'_'+kind)
   assert state_manifest(b,self)['hash']==before['hash'],'PARENT_MUTATED'
  self.branch_output_dir=None
 def finish(self,env,metric):
  super().finish(env,metric)
  if self.child is not None:
   c=self.child;name=c['label']+'_'+c['kind']
   auditrow=audit(name,metric) if c['kind']!='baseline' else dict(activated=0,accepted=0,pass_=metric['valid'] and metric['matched_eligible'])
   record=dict(**c,same_state_verified=True,metric=metric,complete_task_validity=metric['valid'],matched=metric['matched_eligible'],remaining_J_F=metric['J_F']-c['start_J_F'],remaining_moment_integral=metric['moment_integral']-c['start_M'],remaining_duration_s=metric['duration_s']-c['start_task_s'],activated_nonzero=auditrow['activated'],native_audit=auditrow,interpretation='full remaining realized cost under declared native B continuation; not optimal value/Q')
   save(name+'_LABEL.json',record);compact(env.episode_dir);env.close();print(json.dumps(dict(branch=name,valid=metric['valid'],remaining_J_F=record['remaining_J_F'],activated=auditrow['activated'])),flush=True);os._exit(0)
  comparisons=[]
  for target in self.targets:
   label=target['label'];baseline=read(label+'_baseline_LABEL.json');base=np.load(O/(label+'_baseline')/'native_reference.npz')
   for kind in ('hip','knee'):
    row=read(label+'_'+kind+'_LABEL.json');ref=np.load(O/(label+'_'+kind)/'native_reference.npz');different=base['data'].shape!=ref['data'].shape or not np.array_equal(base['data'][:,1:],ref['data'][:,1:])
    delta=row['remaining_J_F']-baseline['remaining_J_F'];comparisons.append(dict(snapshot=label,candidate=kind,same_state=row['snapshot_hash']==baseline['snapshot_hash'],activated=row['activated_nonzero'],reference_differs=different,remaining_J_F_difference=delta,remaining_M_difference=row['remaining_moment_integral']-baseline['remaining_moment_integral'],valid=row['complete_task_validity'],matched=row['matched']))
  valid=len(self.branch_rows)==12 and all(r['complete_task_validity'] and r['matched'] and r['same_state_verified'] for r in self.branch_rows)
  distinct=all(x['same_state'] and x['activated']>0 and x['reference_differs'] for x in comparisons)
  costs=any(abs(x['remaining_J_F_difference'])>1e-6 for x in comparisons)
  save('BRANCH_GATE.json',dict(pass_=valid and distinct and costs,complete_valid=valid,distinct_execution=distinct,cost_differences=costs,comparisons=comparisons,rows=self.branch_rows))
def freeze():
 assert read('MINIMAL_GATE.json')['pass_']
 art=json.loads((S/'results/coordination_research_interface_v1/B_original/summary.json').read_text());spec=registered_task_endpoints();start=np.asarray(spec['start_return_target_rad']);goal=np.asarray(spec['outbound_goal_target_rad']);targets=[]
 for label,phase,index in [('early_OUTBOUND','OUTBOUND',0),('mid_OUTBOUND','OUTBOUND',2),('late_OUTBOUND','OUTBOUND',3),('mid_RETURN','RETURN',2)]:
  d=[d for d in art['decisions'] if d['phase']==phase][index];q=np.asarray(d['deployable_state_rad_rad_s'][:2])+np.asarray(d['executed_action_delta_q_rad']);origin,span=(start,goal-start) if phase=='OUTBOUND' else (goal,start-goal);p=(q-origin)/span
  targets.append(dict(label=label,phase=phase,native_index=index,nominal_target_m=float(np.mean(p)),nominal_target_progress=p.tolist(),baseline_phase_elapsed_s=d['phase_elapsed_s']))
 save('BRANCH_CONTRACT.json',dict(targets=targets,amplitude=.01,graph_half_width=.04,physics_owners=1,rollouts=12,snapshot_rule='before original request snapshot serialization, at native decision opportunity; late is last bidirectionally interior native target (not settled endpoint at phase clock 7.5s)',fork='reuse v1 full process fork; add lifecycle/request/arguments to verification manifest',endpoint='zero action outside declared progress chunk and all other phases',truth_firewall='frozen nominal target coordinates only; hidden full state used solely for fork and evaluation'))
if __name__=='__main__':
 if not (L/'BRANCH_CONTRACT.json').exists():freeze()
 run('branch_parent_v2',Branches())

