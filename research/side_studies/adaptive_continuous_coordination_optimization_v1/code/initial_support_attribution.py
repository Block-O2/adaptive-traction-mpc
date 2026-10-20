"""Original support holding grid duration versus actual host command write."""
from task_bootstrap import *
from stream_runtime_evidence import array_items
from causal_timing_report import quantile
from collections import defaultdict
def main():
 host=json.loads((STUDY/'reports/HOST_QUALIFICATION_SUMMARY.json').read_text());rows=[]
 for run in host['rows']:
  p=STUDY/'source/results'/run['id']/'runtime_artifacts.json.gz';receipts=list(array_items(p,'command_receipts'));support=[r for r in receipts if r.get('receipt_index')==0];assert len(support)==1;support=support[0];epoch=support['active_hold_start_ns'];written=[r for r in receipts if r.get('applied') and r.get('apply_ns') is not None];first=min(written,key=lambda r:r['apply_ns']) if written else None
  generator=array_items(p,'native_states_evaluation_only');state=next(generator,None);generator.close()
  row=dict(id=run['id'],method=run['method'],timing_version=run['timing_version'],public_version=run['public_version'],series=run['host_series'],initial_support_origin=support['origin'],support_native_steps=support['native_steps'],support_grid_duration_ms=support['native_steps']*.25,support_grid_over5ms=support['native_steps']>20,first_step_computation_after_epoch_ms=None if state is None else (state['host_step_start_ns']-epoch)/1e6,first_actual_write_after_epoch_ms=None if first is None else (first['apply_ns']-epoch)/1e6,first_actual_conservative_activation_after_epoch_ms=None if first is None else (first['conservative_activation_ns']-epoch)/1e6,first_write_minus_its_effective_grid_ms=None if first is None else (first['apply_ns']-first['effective_activation_ns'])/1e6,first_write_sensor_age_ms=None if first is None else first.get('sensor_age_at_apply_ms'),first_actual_receipt=None if first is None else first['receipt_index'],full_valid=run['full_task_valid'],TASK_reached=bool(run['task_requests']))
  rows.append(row)
 groups=defaultdict(list)
 for r in rows:groups['/'.join((r['method'],r['timing_version'],str(r['public_version']),r['series']))].append(r)
 fields=('support_grid_duration_ms','first_step_computation_after_epoch_ms','first_actual_write_after_epoch_ms','first_write_minus_its_effective_grid_ms')
 compact={k:dict(attempts=len(v),support_grid_over5ms=sum(r['support_grid_over5ms'] for r in v),timings={field:quantile([r[field] for r in v if r[field] is not None]) for field in fields}) for k,v in groups.items()}
 out=dict(status='INITIAL_SUPPORT_GRID_AND_ACTUAL_HOST_HOLD_SEPARATED',rows=rows,attempts=len(rows),support_grid_gap_epochs=sum(r['support_grid_over5ms'] for r in rows),first_actual_write_over5ms=sum(r['first_actual_write_after_epoch_ms'] is not None and r['first_actual_write_after_epoch_ms']>5 for r in rows),all_cohort_timing={field:quantile([r[field] for r in rows if r[field] is not None]) for field in fields},groups=compact,physics_added=0,interpretation='Support is validated/applied offline before the active epoch, not a late proposed action. Active-epoch original receipt grid duration and actual host write duration differ under fixed-ready catch-up. These data do not assign the whole initial duration to interpreter startup: process prewarm precedes the epoch, while original sensor/observer/reference-history and commissioning/current-command work remain after it. No epoch origin, physics state, source stamp or independent20-step threshold is changed.')
 save(STUDY/'reports/INITIAL_SUPPORT_ATTRIBUTION.json',out);print(json.dumps({k:v for k,v in out.items() if k not in ('rows','groups')}))
if __name__=='__main__':main()
