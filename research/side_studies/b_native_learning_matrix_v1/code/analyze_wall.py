"""Actual host-clock physics qualification; no scientific-cost ranking."""
from task_bootstrap import *
import gzip,statistics

def requests_from_header(p):
 with gzip.open(p,'rt') as f:header=f.read(2**21)
 start=header.find('"requests":')
 if start<0:return []
 try:rows,_=json.JSONDecoder().raw_decode(header[start+11:].lstrip());return rows
 except json.JSONDecodeError:return []

def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1';rows=[]
 for p in sorted([*(STUDY/'queue').glob('070_'+version+'_*.json'),*(STUDY/'queue').glob('075_'+version+'_*.json')]):
  req=json.loads(p.read_text());result=Path(req['result_path']);assert result.exists(),'WALL_TASK_NOT_FINISHED'
  r=json.loads(result.read_text());rescored=STUDY/'output'/(req['id']+'_RESCORED_RESULT.json');sc=json.loads(rescored.read_text()) if rescored.exists() else r;m=sc.get('metric',{});folder=STUDY/'source/results'/req['id'];summary_path=folder/'summary.json';summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
  timing=summary.get('timing',{}).get('requests',[])
  if not timing and (folder/'runtime_artifacts.json.gz').exists():timing=requests_from_header(folder/'runtime_artifacts.json.gz')
  task=[t for t in timing if t.get('stage')=='TASK'];ages=[t['activation_age_ms'] for t in task if t.get('activation_age_ms') is not None];selection_path=STUDY/'output'/(req['id']+'_SELECTIONS.json');selection=json.loads(selection_path.read_text()) if selection_path.exists() else {};ss=selection.get('rows',[])
  partial_path=STUDY/'output'/(req['id']+'_PARTIAL_COMPUTE.json');partial=json.loads(partial_path.read_text()) if partial_path.exists() else None
  audit=m.get('physical_audit',{}).get('unchanged_evaluator',{});valid=bool(m.get('valid'))
  row=dict(id=req['id'],method=req['method'],execution_mode=req['execution_mode'],worker_status=r['status'],error=r.get('error'),valid=valid,status=m.get('status',summary.get('status')),abort_reason=summary.get('abort_reason'),J_F_unranked=m.get('J_F'),phase_durations=m.get('phase_durations'),physical_task_result=audit.get('physical_task_result'),realtime_execution_validity=audit.get('realtime_execution_validity'),partial_compute=partial,task_requests=len(task),activated_task_requests=len(ages),native_activation_max_ms=max(ages) if ages else None,native_55ms_exceed_count=sum(x>55+1e-9 for x in ages),coordinator_decisions=len(ss),coordinator_max_ms=max([s['end_to_end_s']*1000 for s in ss] or [0]),late_discards=sum(s['late_discard'] for s in ss),learning_new_plans_applied=sum(s['plan_changed'] and not s['late_discard'] for s in ss),P_calls=r.get('P_full_performance_calls',selection.get('P_performance_calls')),requests=timing)
  row['online_qualified']=bool(valid and task and len(ages)>0 and all(x<=55+1e-9 for x in ages) and not any(s['late'] for s in ss))
  rows.append(row)
 out=dict(version=version,rows=rows,qualified_methods=[r['method'] for r in rows if r['online_qualified']],physical_costs_not_ranked=True,source='unchanged WallPhysicsSession actually advances physics under host delays; no scientific frozen epoch',interface_admission='new decisions missing conservative native budget discarded; unchanged native lifecycle owns stale-plan rejection and safe fallback',legacy_label_note='selection delay_mode text may say shadow replay, but request execution_mode and original wall_session identify actual host-clock physics here',pilot_qualification='requires repeated scientific learning benefit plus qualified actual online learning execution; fallback-only B behavior is not promoted as online learning benefit')
 save(STUDY/('WALL_ANALYSIS_'+version+'.json'),out)
 print(json.dumps([{k:r[k] for k in ('method','worker_status','valid','error','abort_reason','task_requests','coordinator_decisions','late_discards','online_qualified')} for r in rows]))
if __name__=='__main__':main()
