"""Read-only original realtime receipt/old-command evidence, never a replay."""
from task_bootstrap import *
from stream_runtime_evidence import array_items
from causal_timing_report import quantile
from collections import Counter

def main():
 rows=[]
 for p in sorted((STUDY/'output').glob('*_RESULT.json')):
  result=json.loads(p.read_text());cfg=result.get('inputs',{})
  if cfg.get('execution_mode')!='REALTIME_CHARACTERIZATION':continue
  id=result['id'];folder=STUDY/'source/results'/id;artifact=folder/'runtime_artifacts.json.gz'
  if not artifact.exists():
   rows.append(dict(id=id,raw_artifact_present=False,error=result.get('error')));continue
  receipts=list(array_items(artifact,'command_receipts'));catchups=list(array_items(artifact,'catchup_intervals'))
  held=[r for r in receipts if r.get('applied') and r.get('native_steps',0)>0];gaps=[r for r in receipts if r.get('native_steps',0)>20]
  summary=json.loads((folder/'summary.json').read_text()) if (folder/'summary.json').exists() else {}
  gap_records=[{k:r.get(k) for k in ('receipt_index','native_steps','start_physics_s','end_physics_s','source_capture_ns','effective_activation_ns','conservative_activation_ns','plan_request_id','reference_source','origin')} for r in gaps]
  rows.append(dict(id=id,raw_artifact_present=True,method=cfg.get('method'),timing_version=cfg.get('timing_version'),valid=result.get('metric',{}).get('valid',False),error=result.get('error'),abort_reason=summary.get('abort_reason'),receipt_count=len(receipts),physically_held_receipts=len(held),command_gap_receipts=len(gaps),command_hold_ms=quantile([r['native_steps']*.25 for r in held]),catchup_interval_count=len(catchups),catchup_rows=catchups,gap_records=gap_records,first_active_support_gap=bool(gaps and gaps[0].get('receipt_index')==0)))
 out=dict(status='READ_ONLY_ACTUAL_WALL_EVIDENCE',rows=rows,attempts=len(rows),with_receipt_gaps=sum(r.get('command_gap_receipts',0)>0 for r in rows),with_initial_support_gap=sum(r.get('first_active_support_gap',False) for r in rows),command_gap_denominator='Each original receipt in the complete active physical epoch; includes commissioned support receipt zero as the original independent evaluator does.',registered_native_dt_ms=.25,original_command_gap_threshold_native_steps=20,strict_activation_age_ms='<55',interpretation='A TASK request can be ACTIVATED before generic100 yet fail strict55. Independently, any >20-step command hold or missed control cycle fails realtime qualification, including before TASK. These are held old physical commands, not retroactively supplied feedback. Partial/failed epochs are not complete valid tasks.',no_physics_added=True,no_evaluator_or_control_edits=True)
 save(STUDY/'reports/HOST_FAILURE_FORENSICS.json',out);print(json.dumps({k:out[k] for k in ('status','attempts','with_receipt_gaps','with_initial_support_gap')}))
if __name__=='__main__':main()
