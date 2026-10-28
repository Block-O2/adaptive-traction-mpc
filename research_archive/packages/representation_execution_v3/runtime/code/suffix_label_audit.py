"""Offline label eligibility, never a Q update or a future reward inference."""
from task_bootstrap import *
import numpy as np
from learning_execution_audit import audit
def remaining_mask(plan,count):
 p=np.asarray(plan).copy()
 for j,phase in enumerate(('OUTBOUND','RETURN')):p[j,:min(5,count[phase])]=0.
 return p
def main():
 rows=[]
 ids=sys.argv[1:] or [p.name[:-len('_SELECTIONS.json')] for p in sorted((STUDY/'output').glob('*_SELECTIONS.json')) if (STUDY/'output'/(p.name[:-len('_SELECTIONS.json')]+'_RESULT.json')).exists()]
 for id in ids:
  resultp=STUDY/'output'/(id+'_RESULT.json');sp=STUDY/'output'/(id+'_SELECTIONS.json')
  assert resultp.exists() and sp.exists(),'MISSING_REQUESTED_LABEL_AUDIT_INPUT:'+id
  result=json.loads(resultp.read_text());selections=json.loads(sp.read_text()).get('rows',[]);folder=STUDY/'source/results'/id
  if result.get('inputs',{}).get('method')!='M2' or not selections:continue
  if not (folder/'trace.npz').exists():continue
  evidence=audit(id);owners={r['request_id']:r for r in evidence['rows']}
  with np.load(folder/'trace.npz') as z:
   task=z['stage']=='TASK';times=z['time_s'][task];force=np.linalg.norm(z['physical_cuff_force_world_n'][task],axis=1);increments=force[:-1]*np.diff(times);suffix=np.r_[np.cumsum(increments[::-1])[::-1],0.]
  if not len(times):continue
  local=[]
  for i,s in enumerate(selections):
   own=owners.get(s['request_id'],{});replaced=None
   for nxt in selections[i+1:]:
    # Compare only still-unissued entries at that later native boundary.
    if not np.array_equal(remaining_mask(s['applied_plan'],nxt['count_before']),remaining_mask(nxt['applied_plan'],nxt['count_before'])):replaced=nxt;break
   source=s['physical_source_s'];start=int(np.searchsorted(times,source,side='left'));start=min(start,len(times)-1);executed=own.get('learning_action_execution_proven',False)
   eligible=bool(result.get('metric',{}).get('valid') and executed and replaced is None and not s.get('late_discard'))
   end=float(times[-1]) if replaced is None else float(replaced['physical_source_s']);stop=min(int(np.searchsorted(times,end,side='left')),len(times)-1)
   row=dict(request_id=s['request_id'],selected_source=s['selected_source'],native_current_action=own.get('applied_current_K3_action'),source_physics_s=source,trace_source_s=float(times[start]),actual_nonzero_action_execution_proven=executed,late_discard=bool(s.get('late_discard')),remaining_graph_replaced=replaced is not None,replacement_request_id=None if replaced is None else replaced['request_id'],replacement_physics_s=None if replaced is None else replaced['physical_source_s'],compatible_complete_remaining_cost_label=eligible,remaining_cost_N_s=float(suffix[start]) if eligible else None,censored_cost_before_replacement_N_s=float(suffix[start]-suffix[stop]) if replaced is not None and executed else None,censored_cost_used_as_complete_Q_target=False)
   local.append(row)
  rows.append(dict(id=id,execution_mode=result['inputs'].get('execution_mode'),full_task_valid=result.get('metric',{}).get('valid',False),rows=local,eligible_complete_labels=sum(r['compatible_complete_remaining_cost_label'] for r in local),censored_replacement_labels=sum(r['remaining_graph_replaced'] and r['actual_nonzero_action_execution_proven'] for r in local),labels_used_for_training=0))
 out=dict(status='AUDITED_NO_UPDATE',rows=rows,aggregate=dict(runs=len(rows),eligible_complete_labels=sum(r['eligible_complete_labels'] for r in rows),censored_replacement_labels=sum(r['censored_replacement_labels'] for r in rows),labels_used_for_training=0),no_Q_update=True,no_reward_from_future_repetition=True,label_cost='existing measured-force left quadrature from current native source state until current repetition end only',limitation='Complete suffix compatibility is proven at declared K3 graph level across all subsequent saved native selections plus original actual owner/receipt execution evidence. This is an audit, not a new certified training dataset. SCI host freeze cannot satisfy actual-clock adaptation gate; censored costs are never silently used as complete remaining cost labels.',Q_weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'))
 report=STUDY/'reports/SUFFIX_LABEL_AUDIT.json'
 if report.exists():shutil.copy2(report,STUDY/'reports'/('SUFFIX_LABEL_AUDIT_HISTORY_'+sha(report)+'.json'))
 save(report,out);print(json.dumps(dict(status=out['status'],runs=[{k:r[k] for k in ('id','eligible_complete_labels','censored_replacement_labels','labels_used_for_training')} for r in rows])))
if __name__=='__main__':main()
