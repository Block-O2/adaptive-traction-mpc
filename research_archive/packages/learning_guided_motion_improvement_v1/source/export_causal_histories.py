"""Completed full-TASK causal allowlist export; no truth-state/physics inputs."""
from pathlib import Path
import json,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime'
def main():
 audit=json.loads((P/'audit/INDEPENDENT_RAW_AUDIT.json').read_text());rows=[]
 fields=['time_s','estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','physical_cuff_force_world_n','physical_cuff_moment_world_nm']
 for row in audit['rows']:
  if row['status']!='PASS':continue
  ident=row['id'];trace=R/'source/results'/ident/'trace.npz';summary=json.loads((trace.parent/'summary.json').read_text())
  with np.load(trace) as z:
   task=z['stage']=='TASK';data={k:z[k][task].copy() for k in fields}
  assert not any('evaluation_only' in k or 'true' in k for k in data),'TRUTH_ARRAY_NOT_ALLOWED'
  ph=np.full(len(data['time_s']),'OUTBOUND',dtype='<U10')
  for tr in summary['task']['phase_transitions']:
   if tr['to'] in ['OUTBOUND','HOLD','RETURN']:ph[data['time_s']>=tr['time_s']-1e-9]=tr['to']
  data['phase']=ph;out=P/'history'/(ident+'_FULL_TASK_CAUSAL_HISTORY.npz');np.savez_compressed(out,**data)
  rows.append({'id':ident,'path':str(out.relative_to(P)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_trace_sha256':row['input_sha256'][str(trace.relative_to(P))],'rows':len(ph),'time_start_s':float(data['time_s'][0]),'time_end_s':float(data['time_s'][-1]),'inherited_fork_prefix_included':True,'no_new_native_steps':True,'source_timestamp_note':'time_s is original physical boundary time, not a fabricated sensor request timestamp; live suffix history separately preserves original request source timestamp','physical_cuff_signal_scope':'completed cuff-wrench measurement trace; not hidden Human q/dq','model_source':'summary commissioned handoff_belief is estimated; true Human parameters excluded'})
 (P/'audit/FULL_TASK_CAUSAL_HISTORY_EXPORT.json').write_text(json.dumps({'status':'PASS','allowlist':fields,'exports':rows,'original_live_history_scope':'<attempt>_CAUSAL_HISTORY.json directly samples only the fork suffix; these full-TASK allowlists also preserve inherited physically executed prefix','no_future_target_inputs_or_current_optimizer_updates':True,'deployment_patient_motion_margin_still_NOT_VALIDATED':True},indent=2)+'\n')
 with (P/'CROSS_CYCLE_INTERFACE_PROPOSAL.md').open('a') as out:out.write('\n本包还交付每个完整attempt的FULL_TASK_CAUSAL_HISTORY.npz，只导出已完成trace中的estimated state、issued reference、cuff wrench和boundary time，包含共享物理prefix。直接live采样的原CAUSAL_HISTORY.json只覆盖fork suffix；其request source timestamp仍单列保留。完整导出不伪造缺失的传感器source时间，不含native true Human状态，详见audit/FULL_TASK_CAUSAL_HISTORY_EXPORT.json。\n')
 print('FULL_TASK_CAUSAL_HISTORY_EXPORTED',len(rows),flush=True)
if __name__=='__main__':main()
