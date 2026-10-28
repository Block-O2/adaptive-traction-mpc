"""Read-only causal attribution, including failed and partial physical epochs."""
from pathlib import Path
import sys,json,time
import numpy as np
S=Path('/home/hank/ihear-lab/smoothness_critic_integration_v6/runtime')
sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
from audit import quantile
def main(ident):
 path=S/'source/results'/ident/'runtime_artifacts.json.gz'
 receipts=list(array_items(path,'command_receipts'));intervals=list(array_items(path,'catchup_intervals'));intervals.sort(key=lambda r:r['host_start_ns'])
 states=0;step_ms=[];inside=[0.]*len(intervals);counts=[0]*len(intervals);k=0;provenance_errors=[]
 applied=[r for r in receipts if r.get('applied')];held=[r for r in applied if r.get('native_steps',0)>0];previous=None;receipt_index=0;before_write_steps=0;grid_before_write=0;max_grid_before_write_ns=0;command_mismatches=0
 for row in array_items(path,'native_states_evaluation_only'):
  states+=1
  hs=row.get('host_step_start_ns');hf=row.get('host_step_finish_ns')
  if hs is None or hf is None:continue
  if hf<hs:provenance_errors.append('STEP_NEGATIVE_HOST_TIME')
  elapsed=(hf-hs)/1e6;step_ms.append(elapsed)
  while k<len(intervals) and hs>=intervals[k]['host_end_ns']:k+=1
  if k<len(intervals) and intervals[k]['host_start_ns']<=hs and hf<=intervals[k]['host_end_ns']:inside[k]+=elapsed;counts[k]+=1
  if previous is not None and abs(row['time_s']-previous-.00025)>1e-9:provenance_errors.append('NATIVE_GRID_DIFFERENCE')
  previous=row['time_s']
  while receipt_index<len(held) and row['time_s']>held[receipt_index]['end_physics_s']+1e-9:receipt_index+=1
  if receipt_index<len(held):
   receipt=held[receipt_index]
   if receipt.get('apply_ns') is not None:
    if hs<receipt['apply_ns']:before_write_steps+=1
    effective=receipt.get('effective_activation_ns')
    if effective is not None:
     grid=effective+round((row['time_s']-.00025-receipt['start_physics_s'])*1e9)
     lag=receipt['apply_ns']-grid
     if lag>0:grid_before_write+=1;max_grid_before_write_ns=max(max_grid_before_write_ns,lag)
   if receipt.get('command_torque_nm') is not None and not np.array_equal(np.asarray(row['command_torque_nm']),np.asarray(receipt['command_torque_nm'])):command_mismatches+=1
 scopes=[]
 for i,r in enumerate(intervals):
  ms=(r['host_end_ns']-r['host_start_ns'])/1e6
  scopes.append(dict(reason=r['reason'],start_ns=r['host_start_ns'],finish_ns=r['host_end_ns'],steps=r['native_steps'],total_ms=ms,inside_native_step_ms=inside[i],outside_native_step_ms=ms-inside[i],physical_ms=r['native_steps']*.25,compute_physical_ratio=ms/(r['native_steps']*.25) if r['native_steps'] else None,backlog_ms=r['quantization_or_backlog_ns']/1e6))
 groups={}
 for reason in set(r['reason'] for r in scopes):
  rs=[r for r in scopes if r['reason']==reason]
  groups[reason]=dict(n=len(rs),total_ms=quantile([r['total_ms'] for r in rs]),inside_native_step_ms=sum(r['inside_native_step_ms'] for r in rs),outside_native_step_ms=sum(r['outside_native_step_ms'] for r in rs),compute_physical_ratio=quantile([r['compute_physical_ratio'] for r in rs]))
 ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());requests=ev['native_requests'];task=[r for r in requests if r['stage']=='TASK'];activated=[r for r in task if r['outcome']=='ACTIVATED']
 fields=('snapshot_ms','queue_ms','compute_ms','worker_to_main_scheduling_ms','validation_and_command_construction_ms','activation_age_ms','disposition_age_ms')
 pipeline={f:quantile([r.get(f) for r in task]) for f in fields}
 co=S/'output'/(ident+'_COMMISSIONING_OWNER.json')
 commissioning=json.loads(co.read_text()) if co.exists() else None
 out=dict(id=ident,provenance_errors=provenance_errors,native_steps=states,native_step_ms=quantile(step_ms),native_step_mean_ms=sum(step_ms)/len(step_ms) if step_ms else None,native_steps_over250us=sum(v>.25 for v in step_ms),receipt_count=len(receipts),hold_ms=quantile([r['native_steps']*.25 for r in applied if r.get('native_steps',0)>0]),command_gap_receipts=sum(r.get('native_steps',0)>20 for r in applied),receipt_native_steps=sum(r.get('native_steps',0) for r in applied),step_receipt_count_matches=states==sum(r.get('native_steps',0) for r in applied),catchups=groups,scopes=scopes,task_pipeline=pipeline,strict55_activation_miss_rate=sum(r['activation_age_ms']>=55 for r in activated)/len(activated) if activated else None,strict55_denominator=len(activated),original_requests=requests,commissioning_owner=commissioning,interpretation='Recorded native-step host bracket includes plant.step_native plus small receipt bookkeeping. Catchup residual includes observer/capture, copies and loop interruption, not all noncritical diagnostics. All failed prefixes retained; zero TASK denominator stays censored. Actual old-control integration is not free physics waiting.')
 out.update(new_command_steps_computed_before_host_write=before_write_steps,nominal_grid_step_starts_before_actual_host_write=grid_before_write,max_nominal_grid_before_host_write_ms=max_grid_before_write_ns/1e6,receipt_command_mismatches=command_mismatches,original_fixed_grid_delay_limit='A nominal grid start before actual host write is retained as adverse evidence. It does not imply timely continuous physical execution; all actual computation must occur after the applied receipt.')
 (S/'reports'/(ident+'_FORENSICS.json')).write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ('id','native_steps','native_step_ms','native_step_mean_ms','command_gap_receipts','task_pipeline','strict55_activation_miss_rate')}),flush=True)
if __name__=='__main__':
 for ident in sys.argv[1:]:main(ident)
