from audit_common import *
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,importlib.util
spec=importlib.util.spec_from_file_location('frozen_networks',OLD/'code/inference.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def unique_rows(rows,count=None):
 seen=set();out=[]
 for row in rows:
  plan=np.asarray(row['plan']).copy()
  if count:
   for i,p in enumerate(('OUTBOUND','RETURN')):plan[i,:count[p]]=0
  key=plan.tobytes()
  if key in seen:continue
  seen.add(key);out.append(row)
 return out
def ranking_metrics(rows,network,count=None):
 rows=unique_rows([r for r in rows if not r['rejected']],count)
 if not rows:return dict(accepted_unique=0)
 p=np.array([r['prediction']['total_cost'] for r in rows]);v=np.array([network.value(np.asarray(r['prediction']['terminal']['feature'],np.float32)) for r in rows]);pv=p+v
 a=np.argsort(p,kind='stable');b=np.argsort(pv,kind='stable');k=min(3,len(rows))
 rp=np.empty(len(a));rv=rp.copy();rp[a]=np.arange(len(a));rv[b]=np.arange(len(b))
 gap=float(p[a[1]]-p[a[0]]) if len(a)>1 else None
 return dict(accepted_unique=len(rows),top1_changed=int(a[0])!=int(b[0]),top3_set_changed=set(a[:k])!=set(b[:k]),top3_order_changed=list(a[:k])!=list(b[:k]),rank_correlation=float(np.corrcoef(rp,rv)[0,1]) if len(a)>1 else None,deltaV_min_max=[float(v.min()),float(v.max())],deltaV_dynamic_range=float(np.ptp(v)),P_top1_top2_gap=gap,correction_range_to_gap=None if gap is None or gap<1e-12 else float(np.ptp(v)/gap),P_choice=int(a[0]),PV_choice=int(b[0]),P_rank=a.tolist(),PV_rank=b.tolist())
def main():
 networks={str(p):module.Networks(p) for p in OLD.glob('weights_v2*/networks.npz')}
 records=[(p,read(p)) for p in (OLD/'output').glob('*_DATA.json')];errors=[];checks=[];training_samples=[];timelines=[];state_predictions=[]
 for path,r in records:
  for index,row in enumerate(r.get('value_rows',[])):
   if 'input' not in row:continue
   x=np.asarray(row['input'],np.float32).copy();pending=x[58:88].reshape(2,5,3);plan=np.asarray(r['table'],np.float32).copy()
   for i,phase in enumerate(('OUTBOUND','RETURN')):plan[i,:row['count'][phase]]=0;pending[i,:row['count'][phase]]=0
   remaining=r['metric']['J_F']-row['prefix_J_F'];prediction=row['model_prediction'];base=prediction['total_cost']
   raw_x=np.asarray(row['input'],np.float32);raw_past_nonzero=0
   for i,phase in enumerate(('OUTBOUND','RETURN')):raw_past_nonzero+=int(np.count_nonzero(raw_x[58:88].reshape(2,5,3)[i,:row['count'][phase]]))
   e=dict(file=str(path),index=index,raw_past_nonzero=raw_past_nonzero,remaining_arithmetic_error=abs(remaining-row['remaining_J_F']),delta_arithmetic_error=abs(remaining-base-row['deltaV_label']),base_error=abs(base-row['V_base']),near_base_partition_error=abs(base-prediction['near_cost']-prediction['V_base']),pending_conditioning_equal=bool(np.array_equal(pending,plan)),previous_residual_equal=bool(np.array_equal(x[55:58],np.asarray(row['context']['richer_previous_residual'],np.float32))),continuation_id_equal=row['continuation_version']==r['continuation_version']=='native-certified-committed-K3-suffix-v1',task_start=row['context']['task_s'],phase=row['context']['phase'],counts=row['count'],completion_status=r['metric']['status'],model_terminal_same_phase=prediction['terminal']['phase']==row['context']['phase'])
   checks.append(e)
   if any(e[k]>1e-7 for k in ('remaining_arithmetic_error','delta_arithmetic_error','base_error','near_base_partition_error')) or not all(e[k] for k in ('pending_conditioning_equal','previous_residual_equal','continuation_id_equal','model_terminal_same_phase')):errors.append(e)
   if r['split']=='train' and row['feasible_success']:training_samples.append(x)
   if row['feasible_success'] and not path.name.startswith(('parent_train_','parent_dev_')):
    weight=str(OLD/'weights_v2_seed2026100602/networks.npz');net=networks[weight];delta=net.value(x)
    state_predictions.append(dict(source=str(path),split=r['split'],node=index,model_error=base-remaining,corrected_error=base+delta-remaining,delta_prediction=delta,delta_target=row['deltaV_label']))
 save(STUDY/'LABEL_CONSISTENCY.json',dict(status='PASS' if not errors else 'FAIL',checked_rows=len(checks),raw_saved_rows_with_past_nonzero=sum(r['raw_past_nonzero']>0 for r in checks),effective_masking_basis='frozen v2 training explicitly remaps executed rows by recorded counts; inference feature masks before network; raw historical DATA never rewritten',errors=errors,checks=checks,scope='arithmetic, effective training table masks, previous residual, phase and continuation ids directly checked; analytic versus physical clock/state approximation is separate, not erased by PASS',repetition_boundary='same DATA final current-task metric; no future repetition field or accumulation'))
 actions=[]
 for batch in ('final','fresh','extra'):
  contract=read(OLD/f'COMPARISON_v2_{batch}.json');weight=contract['weights'];net=networks[weight]
  for req in contract.get('requests',[]):pass
  files=[p for p in (OLD/'output').glob(f'*v2_{batch}_*_P_SEARCH.json')]
  for path in files:
   data=read(path)
   for i,row in enumerate(data['rows']):actions.append(dict(batch=batch,file=str(path),decision_index=i,phase=row['context']['phase'],task_s=row['context']['task_s'],**ranking_metrics(row['candidates'],net,row['count_before'])))
   # Each file is processed once; no physical evaluation or fitting.
 summary=dict(states=len(actions),top1_change_count=sum(r.get('top1_changed',False) for r in actions),top3_set_change_count=sum(r.get('top3_set_changed',False) for r in actions),top3_order_change_count=sum(r.get('top3_order_changed',False) for r in actions),mean_rank_correlation=float(np.mean([r['rank_correlation'] for r in actions if r.get('rank_correlation') is not None])),scope='same saved P pool rescore by batch frozen V; counterfactual selection, not actual PV regenerated CEM pool')
 save(STUDY/'V_ACTION_LEVERAGE_OLD.json',dict(summary=summary,states=actions))
 xtrain=np.asarray(training_samples);coverage=[]
 for case in read(STUDY/'AUDIT_CONTRACT.json')['cases']:
  path=STUDY/'output'/(case['state']+'_POOL.json')
  if not path.exists():continue
  pool=read(path);net=networks[case['weights']]
  for row in pool['rows']:
   x=np.asarray(row['KNOWN']['prediction']['terminal']['feature'],np.float32);w=net.weights;dist=np.sqrt(np.mean(((xtrain-x)/w['V_scale'])**2,axis=1));coverage.append(dict(state=case['state'],identity=row['item']['identity'],nearest_training_normalized_RMS=float(dist.min()),mean_training_normalized_RMS=float(dist.mean()),synthetic_terminal=True))
 save(STUDY/'TERMINAL_FEATURE_COVERAGE.json',dict(training_rows=len(xtrain),rows=coverage,scope='representation distance only; neighboring V rows are correlated, not independent coverage; no threshold invented for clinical/generalization claims'))
 by_split={k:dict(rows=len(sub),model_RMSE=float(np.sqrt(np.mean([r['model_error']**2 for r in sub]))),corrected_RMSE=float(np.sqrt(np.mean([r['corrected_error']**2 for r in sub])))) for k in sorted({r['split'] for r in state_predictions}) for sub in [[r for r in state_predictions if r['split']==k]]}
 save(STUDY/'ACTUAL_NATIVE_VALUE_PREDICTION_ERRORS.json',dict(rows=state_predictions,by_split=by_split,model_RMSE=float(np.sqrt(np.mean([r['model_error']**2 for r in state_predictions]))),corrected_RMSE=float(np.sqrt(np.mean([r['corrected_error']**2 for r in state_predictions]))),no_claim_of_control_improvement=True,scope='non-training non-development files include test and smoke; split counts reported; rows are correlated, not independent states'))
 print(json.dumps(dict(label_rows=len(checks),label_errors=len(errors),old_action_leverage=summary)))
if __name__=='__main__':main()
