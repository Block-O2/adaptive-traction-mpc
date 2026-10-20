from pathlib import Path
import sys,json,re,gzip,collections,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
def quantile(a):return dict(zip(('p50','p95','p99','max'),np.percentile(a,[50,95,99,100]).tolist())) if len(a) else {}
def scalars(path,names):
 found={};tail=''
 with gzip.open(path,'rt') as f:
  while len(found)<len(names):
   block=f.read(65536)
   if not block:break
   text=tail+block
   for n in names:
    if n not in found:
     match=re.search('"'+n+'"\\s*:\\s*([-+0-9.eE]+)',text)
     if match:found[n]=float(match.group(1))
   tail=text[-1024:]
 return found
def main():
 ident=sys.argv[1];result=json.loads((S/'output'/(ident+'_RESULT.json')).read_text());artifact=S/'source/results'/ident/'runtime_artifacts.json.gz'
 if not artifact.exists():
  out=dict(id=ident,status='FAILED_INCOMPLETE',worker_status=result['status'],error=result.get('error'),functional='FAIL',M2_eligible=False);(S/'reports'/(ident+'_FUNCTIONAL.json')).write_text(json.dumps(out,indent=2)+'\n');print(out);return
 import qualification
 legacy=qualification.run(ident)
 evidence=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());services=evidence['rows']['fast'];starts=np.array([r['service_start_ns'] for r in services]);gaps=np.diff(starts)/1e6
 rolling=[];first=0
 for last in range(1,len(starts)):
  while first<last-1 and starts[last]-starts[first+1]>=1_000_000_000:first+=1
  if starts[last]-starts[first]>=990_000_000:rolling.append((starts[last]-starts[first])/(last-first)/1e6)
 receipts=list(array_items(artifact,'command_receipts'));byid={r['receipt_index']:r for r in receipts};step_count=0;violations=[];ownership_counts=collections.Counter();expired=0
 for row in array_items(artifact,'native_states_evaluation_only'):
  step_count+=1;owner=row.get('command_id');ownership_counts[owner]+=1
  if owner is None:violations.append('MISSING_COMMAND_ID');continue
  receipt=byid[owner]
  if receipt.get('apply_ns') is not None:
   if row['native_grid_start_ns']<receipt['apply_ns']:violations.append('GRID_BEFORE_ACTUAL_WRITE')
   if not np.array_equal(np.asarray(row['command_torque_nm']),np.asarray(receipt['command_torque_nm'])):violations.append('TORQUE_OWNER_MISMATCH')
   if receipt.get('sensor_age_at_apply_ms',0)>100.:expired+=1
 applied=[r for r in receipts if r.get('applied') and r.get('apply_ns') is not None];quantization=[r.get('quantization_delay_ns',float('inf')) for r in applied]
 actual_writes=[r for r in receipts if r.get('apply_ns') is not None]
 expired_actual_writes=[r['receipt_index'] for r in actual_writes if r['apply_ns']-r['source_capture_ns']>100_000_000]
 missing_versions=[r['receipt_index'] for r in applied if r.get('validation_model_version') is None or r.get('reference_version') is None]
 admission=json.loads((S/'output'/(ident+'_ADMISSION_CERTIFICATES.json')).read_text())
 accounted=sum(r.get('native_steps',0) for r in receipts);meta=scalars(artifact,['maximum_backlog_s','current_backlog_s','physics_elapsed_s','origin_physics_s','epoch_ns'])
 protocol=json.loads((S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json').read_text())['required'];q=quantile(gaps)
 checks=dict(full_OUT_HOLD_RETURN=legacy['complete_out_hold_return'],original_physical_safety=(legacy.get('original_physical_task_result') or {}).get('status')=='PASS',original_R2=legacy['original_r2_valid'],meaningful_plans=legacy['physically_executed_meaningful_count']>=protocol['meaningful_plans_min'],causal_substep_command_ownership=not violations and step_count==accounted,quantization_delay=bool(quantization) and min(quantization)>=0 and max(quantization)<=protocol['quantization_delay_ns_max'],expired_writes=expired==0,service_gap_p50=bool(q) and q['p50']<=protocol['service_gap_p50_ms_max'],service_gap_p95=bool(q) and q['p95']<=protocol['service_gap_p95_ms_max'],service_gap_p99=bool(q) and q['p99']<=protocol['service_gap_p99_ms_max'],gap_over_10ms_fraction=bool(len(gaps)) and float(np.mean(gaps>10.))<=protocol['service_gap_over_10ms_fraction_max'],missed_grid_fraction=legacy['miss_rate']<=protocol['missed_grid_fraction_max'],rolling_1s_service_mean=bool(rolling) and max(rolling)<=protocol['rolling_1s_service_mean_ms_max'],bounded_backlog=meta.get('maximum_backlog_s',float('inf'))<=protocol['max_unresolved_backlog_s'])
 checks={k:bool(v) for k,v in checks.items()}
 checks['original_current_state_admission']=bool((legacy.get('original_physical_task_result') or {}).get('activation_certificates_valid') and admission.get('current_state_checks_unchanged'))
 checks['expired_writes']=checks['expired_writes'] and not expired_actual_writes
 checks['causal_substep_command_ownership']=checks['causal_substep_command_ownership'] and not missing_versions
 functional='PASS' if all(checks.values()) else 'FAIL'
 out=dict(id=ident,status='REVIEWED',functional=functional,functional_checks=checks,legacy_strict='PASS' if legacy['qualified'] else 'FAIL',legacy_result=legacy,service_gap_ms=q,rolling_1s_mean_ms=quantile(rolling),gap_over_10_fraction=float(np.mean(gaps>10.)) if len(gaps) else None,actual_native_steps=step_count,receipt_native_steps=accounted,trace_native_steps=result.get('metric',{}).get('native_physics_steps'),native_step_ownership_counts=dict(ownership_counts),causal_violations=collections.Counter(violations),quantization_delay_ns=quantile(quantization),expired_physical_steps=expired,wall_physics=meta,attribution_only=result['inputs'].get('attribution',False),M2_eligible=False,note='Promotion additionally requires independent retest and full cold/same-interpreter ladder; attribution smoke alone cannot qualify.')
 out.update(expired_actual_write_receipts=expired_actual_writes,missing_model_reference_version_receipts=missing_versions,source_model_version_authority='Original validation_model_version on each written receipt, plus source_capture_ns; runtime sequence separately available.',initial_offline_support='Existing validated support before physical epoch; legacy apply_ns=None is retained and never represented as a new active-epoch write.')
 (S/'reports'/(ident+'_FUNCTIONAL.json')).write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ('id','functional','functional_checks','service_gap_ms','actual_native_steps','receipt_native_steps','causal_violations','quantization_delay_ns','wall_physics')}))
if __name__=='__main__':main()
