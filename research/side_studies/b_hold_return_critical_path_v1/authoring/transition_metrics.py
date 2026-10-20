from pathlib import Path
import json,sys,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
def stats(a):return dict(zip(('p50','p95','p99','max'),np.percentile(a,[50,95,99,100]).tolist())) if a else {}
def main():
 ident=sys.argv[1];sp=S/'source/results'/ident/'summary.json'
 if not sp.exists():raise SystemExit('No exported physical summary: no completed transition claim.')
 s=json.loads(sp.read_text());m=json.loads((S/'output'/f'{ident}_MULTIRATE.json').read_text());trans=s['task']['phase_transitions']
 entry=next((r for r in trans if r['to']=='HOLD'),None);exit=next((r for r in trans if r['from']=='HOLD' and r['to']=='RETURN'),None)
 if entry is None or exit is None:raise SystemExit('No complete original HOLD to RETURN transition.')
 ds=[d for d in s['decisions'] if d.get('phase')=='HOLD'];ret=next(d for d in s['decisions'] if d.get('phase')=='RETURN')
 reqs={r['request_id']:r for r in m['native_requests']};r=reqs[ret['timing_request_id']]
 artifact=sp.parent/'runtime_artifacts.json.gz';receipts=list(array_items(artifact,'command_receipts'))
 writes=[x for x in receipts if x.get('applied') and x.get('apply_ns') is not None]
 first=min((x for x in writes if x['apply_ns']>=r['validation_finish_ns']),key=lambda x:x['apply_ns'])
 endpoints=[]
 for d in ds:
  start=d['actual_schedule_start_physics_s'];duration=d['evaluations'][0]['schedule']['duration_s']
  matches=[x for x in writes if x.get('reference_progress',{}).get('selected_progress_s',-1)>=duration-1e-12 and start<=x['start_physics_s']<start+duration+.1]
  endpoint=min(matches,key=lambda x:x['apply_ns'])
  endpoints.append(dict(request_id=d['timing_request_id'],actual_reference_start_s=start,actual_endpoint_write_ns=endpoint['apply_ns'],actual_endpoint_physics_s=endpoint['start_physics_s'],receipt_index=endpoint['receipt_index'],nominal_duration_s=duration))
 first_step=next(x for x in array_items(artifact,'native_states_evaluation_only') if x.get('command_id')==first['receipt_index'])
 collection=S/'output'/f'{ident}_HOLD_REQUEST_COLLECTION.json'
 out=dict(id=ident,HOLD_s=exit['time_s']-entry['time_s'],entry_s=entry['time_s'],exit_source_s=exit['time_s'],segments=endpoints,RETURN=dict(request_id=r['request_id'],source_sample_s=r['source_sample_time_s'],source_capture_ns=r['sensor_capture_ns'],request_ns=r['request_ns'],snapshot_finish_ns=r['snapshot_finish_ns'],enqueue_ns=r['enqueue_ns'],worker_start_ns=r['worker_start_ns'],compute_finish_ns=r['compute_finish_ns'],collect_ns=r['result_collected_ns'],validation_start_ns=r['validation_start_ns'],validation_finish_ns=r['validation_finish_ns'],actual_write_ns=first['apply_ns'],lifecycle_activation_return_ns=r['activation_ns'],first_native_grid_ns=first_step['native_grid_start_ns'],first_native_interval_s=first_step['physical_interval_start_s'],request_to_actual_write_ms=(first['apply_ns']-r['request_ns'])/1e6,source_to_actual_write_ms=(first['apply_ns']-r['sensor_capture_ns'])/1e6),all_actual_write_source_age_ms=stats([(x['apply_ns']-x['source_capture_ns'])/1e6 for x in writes]),task_source_to_lifecycle_activation_ms=stats([x['activation_age_ms'] for x in m['native_requests'] if x['stage']=='TASK' and x.get('activation_age_ms') is not None]),collection_services=None if not collection.exists() else json.loads(collection.read_text()),no_cross_run_timestamp_addition=True)
 out['RETURN_nonoverlap_ms']={name:(end-begin)/1e6 for name,begin,end in [
 ('request_snapshot',r['request_ns'],r['snapshot_finish_ns']),('snapshot_enqueue',r['snapshot_finish_ns'],r['enqueue_ns']),('queue',r['enqueue_ns'],r['worker_start_ns']),('compute',r['worker_start_ns'],r['compute_finish_ns']),('ready_collect',r['compute_finish_ns'],r['result_collected_ns']),('collect_validation',r['result_collected_ns'],r['validation_start_ns']),('validation_command',r['validation_start_ns'],r['validation_finish_ns']),('validated_actual_write',r['validation_finish_ns'],first['apply_ns'])]}
 assert abs(sum(out['RETURN_nonoverlap_ms'].values())-out['RETURN']['request_to_actual_write_ms'])<1e-9
 p=S/'reports'/f'{ident}_TRANSITION_METRICS.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(dict(id=ident,HOLD_s=out['HOLD_s'],RETURN=out['RETURN'],segments=endpoints,nonoverlap_closes=True)))
if __name__=='__main__':main()
