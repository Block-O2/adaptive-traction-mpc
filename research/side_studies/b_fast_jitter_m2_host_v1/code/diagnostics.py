"""Read-only causal analysis and source-boundary evidence."""
from pathlib import Path
import json,sys,collections
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1')
sys.path.insert(0,str(S/'code'))
from audit import quantile
def save(n,x):(S/'reports'/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 rows=[]
 for p in sorted((S/'output').glob('*_RESULT.json')):
  result=json.loads(p.read_text());cfg=result.get('inputs',{})
  if cfg.get('execution_mode')!='REALTIME_CHARACTERIZATION':continue
  ident=result['id'];ev=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());fast=ev['rows']['fast'];native=ev['native_requests'];co_path=S/'output'/(ident+'_COMMISSIONING_OWNER.json');co=json.loads(co_path.read_text()) if co_path.exists() else {}
  gaps=[]
  for a,b in zip(fast,fast[1:]):
   start=a['service_start_ns'];finish=b['service_start_ns'];gap=(finish-start)/1e6
   if gap<40:continue
   gaps.append(dict(gap_ms=gap,phase_before=a['phase'],phase_after=b['phase'],feedback_duration_ms=(a['service_finish_ns']-start)/1e6,after_service_ms=(finish-a['service_finish_ns'])/1e6,physics_steps_in_tick=a.get('physical_steps_in_tick'),coinciding_requests=[dict(request_id=q['request_id'],stage=q['stage'],outcome=q['outcome']) for q in native if start<=q.get('request_ns',0)<=finish or start<=q.get('conservative_activation_ns',0)<=finish],commissioning=[q for q in co.get('rows',[]) if start<=q.get('data_available_ns',0)<=finish or start<=q.get('estimate_ready_ns',0)<=finish]))
  planner=ev['rows']['planner'];admission=ev['rows']['admission']
  stages={stage:collections.Counter(q['outcome'] for q in native if q['stage']==stage) for stage in set(q['stage'] for q in native)}
  rows.append(dict(id=ident,series=cfg.get('host_series','development_smoke'),all_original_source_identities_preserved=all(q.get('original_source_identity_preserved',True) for q in planner),collected_proposals=sum('proposal_receive_ns' in q for q in planner),transfer_collection_ms=quantile([(q['transfer_finish_ns']-q['proposal_receive_ns'])/1e6 for q in planner if 'proposal_receive_ns' in q]),snapshot_payload_bytes=quantile([q['payload_bytes'] for q in planner]),current_state_revalidation_ms=quantile([(q['revalidation_finish_ns']-q['revalidation_start_ns'])/1e6 for q in admission]),admission_pass=sum(q['feasible'] for q in admission),admission_fail=sum(not q['feasible'] for q in admission),native_lifecycle_outcomes=stages,commissioning=co,largest_service_gaps=sorted(gaps,key=lambda q:q['gap_ms'],reverse=True)[:12]))
 save('CAUSAL_DIAGNOSTICS.json',rows)
 evidence=[]
 names={'online_planning.py','wall_physics.py','safe_fallback.py','activation_validation.py','campaign_r2.py','mode_metadata.py','physical_audit_v3.py','host_qualification_summary.py','learning_execution_audit.py','evaluate_execution_mode.py','qualify.py'}
 for root in (S/'source',S/'code'):
  for p in root.rglob('*.py'):
   if 'results' in p.parts or p.name not in names:continue
   lines=p.read_text().splitlines()
   for i,line in enumerate(lines):
    if any(token in line for token in ('55.','55_000_000','strict_age_limit','1.020','1.02','100_000_000','0.040','0.04','source_capture_ns','HOST_LATENCY','future.result(','bridge_ticks','PHASE_MIN','DECISION_ALLOWANCE','maximum_age_ns','self.bridge','sensor_capture_ns')):
     evidence.append(dict(path=str(p),line=i+1,context='\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-2),min(len(lines),i+3)))))
 save('SOURCE_TIMING_BOUNDARIES.json',evidence)
 print('diagnosed',len(rows),'source excerpts',len(evidence))
if __name__=='__main__':main()
