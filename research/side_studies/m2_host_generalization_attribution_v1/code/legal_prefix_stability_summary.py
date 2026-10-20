"""CASE4 paired SCI evidence and matched pre-learning causal trajectories."""
from task_bootstrap import *
from stream_runtime_evidence import array_items
from causal_timing_report import quantile
import numpy as np

def prefix_proof(b,m,boundary):
 traces={};issues=[];counts=[];hashes=[]
 for id in (b,m):
  h=hashlib.sha256();n=0
  for row in array_items(STUDY/'source/results'/id/'runtime_artifacts.json.gz','native_states_evaluation_only'):
   if row['time_s']>=boundary-1e-9:break
   values=np.asarray([row['time_s'],*row['qpos_evaluation_only'],*row['qvel_evaluation_only'],*row['command_torque_nm']],dtype='<f8');h.update(values.tobytes());h.update(json.dumps(row['contact_pairs_evaluation_only'],sort_keys=True).encode());n+=1
  counts.append(n);hashes.append(h.hexdigest())
 if counts[0]!=counts[1] or hashes[0]!=hashes[1]:issues.append('PRE_LEARNING_NATIVE_TRAJECTORY_DIFFERENCE')
 with np.load(STUDY/'source/results'/b/'trace.npz') as x,np.load(STUDY/'source/results'/m/'trace.npz') as y:
  for k in x.files:
   if k not in y:issues.append('MISSING_TRACE_FIELD:'+k);continue
   def aligned_times(trace,field):
    if len(trace[field])==len(trace['time_s']):return trace['time_s']
    assert field in ('task_beta','task_residual_weights_nm'),'UNREGISTERED_TRACE_ALIGNMENT:'+field
    task_times=trace['time_s'][trace['stage']=='TASK'];assert len(task_times)==len(trace[field]),'TASK_ONLY_ALIGNMENT'
    return task_times
   a=x[k][aligned_times(x,k)<boundary-1e-9];z=y[k][aligned_times(y,k)<boundary-1e-9]
   if a.shape!=z.shape:issues.append('PREFIX_TRACE_SHAPE:'+k);continue
   if a.dtype.kind in 'fiu':
    same=np.allclose(a,z,rtol=0,atol=1e-10,equal_nan=True);finite=np.isfinite(a)&np.isfinite(z);traces[k]=float(np.max(np.abs(a[finite]-z[finite]))) if np.any(finite) else 0.
   else:same=np.array_equal(a,z)
   if not same:issues.append('PREFIX_TRACE_DIFFERENCE:'+k)
 return dict(status='PASS' if not issues else 'FAIL',issues=issues,boundary_physics_s=boundary,comparison_scope='All native physical states/commands/contacts and all reference/trace fields strictly before first Q selection source state; post-learning differences are intended.',native_steps=counts,native_sha256=hashes,trace_max_errors=traces,tolerance=1e-10)

def main():
 protocol=json.loads((STUDY/'versions/LEGAL_PREFIX_STABILITY_PROTOCOL.json').read_text());rows=[];pending=[]
 for pair in range(1,9):
  declarations=[r for r in protocol['rows'] if r['pair']==pair];cases={}
  for declaration in declarations:
   p=STUDY/'output'/(declaration['id']+'_RESULT.json')
   if not p.exists():pending.append(declaration['id']);continue
   r=json.loads(p.read_text());metric=r.get('metric',{});sp=STUDY/'output'/(r['id']+'_SELECTIONS.json');selections=json.loads(sp.read_text()).get('rows',[]) if sp.exists() else []
   cases[declaration['method']]=dict(id=r['id'],valid=metric.get('valid',False),worker_status=r['status'],error=r.get('error'),J_F=metric.get('J_F') if metric.get('valid') else None,failed_cost_unranked=metric.get('J_F') if not metric.get('valid') else None,moment=metric.get('moment_integral'),force_peak=metric.get('force_peak'),moment_peak=metric.get('moment_peak'),phase_durations=metric.get('phase_durations'),physical_audit=metric.get('physical_audit'),physical_clearance=metric.get('physical_clearance'),clearance=metric.get('clearance'),selection_count=len(selections),selected_sources=[s['selected_source'] for s in selections],coordinator_SCI_ms=quantile([s['end_to_end_s']*1000 for s in selections]),fast_prefix_SCI_ms=quantile([s.get('fast_coordinator_s',s['end_to_end_s'])*1000 for s in selections]),first_Q_source_s=selections[0]['physical_source_s'] if selections else None)
  row=dict(pair=pair,prefix=declarations[0]['prefix'],seed=declarations[0]['seed'],cases=cases)
  if set(cases)=={'M0','M2'} and cases['M0']['valid'] and cases['M2']['valid']:
   b,m=cases['M0'],cases['M2'];row.update(paired_force_reduction_percent=100*(b['J_F']-m['J_F'])/b['J_F'],paired_moment_increase_percent=100*(m['moment']-b['moment'])/b['moment'])
   if m['first_Q_source_s'] is not None:row['matched_pre_learning_prefix_proof']=prefix_proof(b['id'],m['id'],m['first_Q_source_s'])
  rows.append(row)
 valid=[r for r in rows if 'paired_force_reduction_percent' in r]
 out=dict(status='COMPLETE_CASE4_SCI_STABILITY' if not pending else 'PARTIAL_CASE4_SCI_STABILITY',classification=protocol['classification'],rows=rows,pending=pending,valid_pairs=len(valid),planned_pairs=8,positive_pairs=sum(r['paired_force_reduction_percent']>0 for r in valid),B_mean_J_F=float(np.mean([r['cases']['M0']['J_F'] for r in valid])) if valid else None,frozen_mean_J_F=float(np.mean([r['cases']['M2']['J_F'] for r in valid])) if valid else None,mean_paired_reduction_percent=float(np.mean([r['paired_force_reduction_percent'] for r in valid])) if valid else None,mean_paired_moment_increase_percent=float(np.mean([r['paired_moment_increase_percent'] for r in valid])) if valid else None,Q_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),Q_updates=0,host_qualification=False,adaptation=False,no_Human_truth_change=True,interpretation='Eight preregistered distinct lawful prefixes and distinct six-candidate RNG seeds in the exposed nominal Human. SCI validates frozen control benefit, not realtime or Phase C success. Any failed pair is excluded from ranked cost and reported. Shared pre-learning physical prefix must match; later Q actions intentionally differ. Future RETURN prefix interventions can be realized at different start states after OUT learning and are not asserted to be the same realized physical path.')
 save(STUDY/'reports/LEGAL_PREFIX_STABILITY_SUMMARY.json',out);print(json.dumps({k:out[k] for k in ('status','valid_pairs','positive_pairs','pending','B_mean_J_F','frozen_mean_J_F','mean_paired_reduction_percent','mean_paired_moment_increase_percent')}))
if __name__=='__main__':main()
