"""Offline integer-grid reconstruction. Never alters original qualification."""
from pathlib import Path
import json,sys,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
def main():
 ident=sys.argv[1];summary=json.loads((S/'source/results'/ident/'summary.json').read_text());m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text())
 phases=summary['task']['phase_transitions'];entry=next(x for x in phases if x['to']=='HOLD');end=next(x for x in phases if x['from']=='HOLD')
 original=end['time_s']-entry['time_s'];ticks=round(end['time_s']/.00025)-round(entry['time_s']/.00025);exact=ticks*.00025
 decisions=[x for x in summary['decisions'] if x.get('phase')=='HOLD'];reqids={x['timing_request_id'] for x in decisions};reqs=[x for x in m['native_requests'] if x['request_id'] in reqids]
 rows=[]
 for d in decisions:
  r=next(x for x in reqs if x['request_id']==d['timing_request_id'])
  rows.append(dict(request_id=r['request_id'],source_task_time_s=r['source_sample_time_s'],source_capture_ns=r['sensor_capture_ns'],request_ns=r['request_ns'],compute_finish_ns=r['compute_finish_ns'],collected_ns=r['result_collected_ns'],validation_start_ns=r['validation_start_ns'],validation_finish_ns=r['validation_finish_ns'],effective_activation_ns=r['effective_activation_ns'],actual_activation_ns=r['activation_ns'],worker_ms=r['compute_ms'],collection_after_completion_ms=r['worker_to_main_scheduling_ms'],current_validation_ms=r['validation_and_command_construction_ms'],schedule_start_physics_s=d['actual_schedule_start_physics_s'],duration_s=d['selected_plan']['duration_s'] if 'selected_plan' in d and 'duration_s' in d['selected_plan'] else None))
 out=dict(id=ident,unix=time.time(),status='DIAGNOSTIC_COMPLETE',original_HOLD_s=original,integer_native_grid_HOLD_s=exact,native_grid_ticks=ticks,floating_accumulation_difference_s=original-exact,unchanged_R2_HOLD_limit_s=1.02,integer_reconstruction_still_exceeds_R2=exact>1.02,requests=rows,physics_steps=0,model_API_calls=0,no_historical_score_relabel=True,interpretation='Reconstructs observed endpoints only. Floating accumulation cannot explain this measured excess; no global impossibility claim and no task/planner-authority change.')
 (S/'reports'/(ident+'_HOLD_GRID_RECONSTRUCTION.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
