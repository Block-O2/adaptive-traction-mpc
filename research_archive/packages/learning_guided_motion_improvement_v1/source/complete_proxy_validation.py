"""Merge post-lock trajectory validation into the stage-1 proxy evidence."""
from pathlib import Path
import json,hashlib,shutil,datetime
import numpy as np
P=Path(__file__).resolve().parents[1]
def main():
 a=json.loads((P/'OPTIMIZATION_ANALYSIS.json').read_text());proxy=json.loads((P/'PROXY_MODEL_RESULTS.json').read_text());snapshot=P/'history/PROXY_MODEL_RESULTS_ZERO_PHYSICS_FINAL.json'
 if not snapshot.exists():shutil.copyfile(P/'PROXY_MODEL_RESULTS.json',snapshot)
 H=json.loads((P/'runtime/reports/OPTIMIZATION_H150_MEASURED.json').read_text());table=json.loads((P/'models/NOMINAL_PROXY_TABLE.json').read_text());errors={}
 for arm in 'ABC':
  rows=[r for r in a['whole_trajectory_prediction_rows'] if r['arm']==arm];per={}
  for i,ph in enumerate(['OUTBOUND','HOLD','RETURN']):
   actual=np.array([r['phase_actual'][ph] for r in rows]);pred=np.array([H['phase_cost']['phases'][ph]['J_F_N_s']+r['phase_nominal'][ph]-table['center'][2+i] for r in rows]);e=pred-actual;per[ph]={'n_complete_trajectories':len(rows),'nominal_anchored_MAE_N_s':float(np.mean(abs(e))),'nominal_anchored_RMSE_N_s':float(np.sqrt(np.mean(e*e)))}
  errors[arm]=per
 proxy.update(artifact_scope='Historical zero-new-physics diagnostic preserved plus completed local prequential validation; no full robot/contact/motion prediction qualification',historical_diagnostic_new_physical_attempts=0,current_optimizer_attempts=a['attempt_denominators'],current_local_prequential=a['prediction_error_study'],current_phase_nominal_prediction_errors=errors,feedback_firewall=a['feedback_firewall'],current_motion_task_scope={'physics_actual_tracking':'UNKNOWN','physics_actual_v_a_jerk':'UNKNOWN; reference-template derivatives only','physics_excursion_terminal_overshoot':'UNKNOWN for actual Human; template quantities only','physics_task_contact_feasibility':'UNKNOWN','learned_worst_motion_ratio':'limited same-parent offline empirical label model','cross_patient_validated':False,'current_new_legal_prefix':'FROZEN_NEW_PREFIX_RESULTS.json','motion_failure_domain_validation':False if all(a['qualified_counts'][x]==a['complete_counts'][x] for x in 'ABC') else 'inspect actual failed rows'},updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),postlock_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 newfile=P/'FROZEN_NEW_PREFIX_RESULTS.json';frozen_new=None
 if newfile.exists():
  nv=json.loads(newfile.read_text());hr=next((r for r in nv['rows'] if r['id']=='FROZEN_NEW_PREFIX_H150'),None);valrows=[]
  for rr in nv['rows']:
   pp=rr.get('prediction')
   if not pp or not rr.get('complete'):continue
   nominal=pp['baseline_anchored_nominal'][0];learned=pp.get('learned_prediction');lp=None if learned is None else learned[0]
   valrows.append({'id':rr['id'],'x':rr['x'],'qualified':rr['qualified'],'actual_JF':rr['JF'],'frozen_nominal_absolute_JF':nominal,'nominal_absolute_error':nominal-rr['JF'],'frozen_learned_absolute_JF':lp,'learned_absolute_error':None if lp is None else lp-rr['JF'],'frozen_nominal_delta_vs_original_H150':nominal-a['baseline']['JF'],'frozen_learned_delta_vs_original_H150':None if lp is None else lp-a['baseline']['JF'],'actual_delta_vs_new_H150':None if hr is None or not hr['complete'] else rr['JF']-hr['JF'],'new_H150_qualified':False if hr is None else hr['qualified'],'frozen_nominal_absolute_JM':pp['baseline_anchored_nominal'][1],'nominal_absolute_JM_error':pp['baseline_anchored_nominal'][1]-rr['JM'],'frozen_learned_absolute_JM':None if learned is None else learned[1],'learned_absolute_JM_error':None if learned is None else learned[1]-rr['JM'],'frozen_learned_delta_JM_vs_original_H150':None if learned is None else learned[1]-a['baseline']['JM'],'actual_delta_JM_vs_new_H150':None if hr is None or not hr['complete'] else rr['JM']-hr['JM'],'model_updated_or_reanchored_on_new_prefix_for_selection':False})
  frozen_new={'same_Human':1,'independent_legal_prefix_groups':1,'no_new_prefix_model_updates':True,'rows':valrows,'interpretation':'Absolute forecasts retain original anchor; paired deltas are separately diagnosed against matched new H150 after results. No new-baseline reanchoring was used to choose candidates; no cross-patient qualification.'};proxy['frozen_new_prefix_validation']=frozen_new
 (P/'PROXY_MODEL_RESULTS.json').write_text(json.dumps(proxy,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 marker='## 三臂完整轨迹预序验证'
 f=P/'FORWARD_PROXY_VALIDATION.md'
 if marker not in f.read_text():
  c=a['prediction_error_study']['C'];block='\n'+marker+'\n\n'
  block+='完整轨迹分母：'+str(a['complete_counts'])+'；同一优化父状态组，不能按时间步或次数冒充独立患者。每次预测早于其START，且只使用自身先前反馈，见OPTIMIZATION_ANALYSIS.json的feedback_firewall。\n\n'
  block+=f"C在自己真实执行点上的名义锚定JF RMSE={c['force_nominal_anchored']['RMSE']:.9f} N·s，学习预序RMSE={c['force_learned_prequential']['RMSE']:.9f}。该预测比较与C是否找到更好的实际运动独立；固定12次C超过A/B={a['C_better_than_A_B_at12']}，全分配={a['C_better_than_A_B_all']}。\n\n"
  block+='分phase名义预测误差见PROXY_MODEL_RESULTS.json的current_phase_nominal_prediction_errors；完整JM、收益符号、排序与不确定性经验覆盖见MODEL_RESIDUAL_RESULTS.json。原真实tracking/native derivative/excursion/overshoot/task/contact的完整事前闭包仍未建立，原安全链拥有最终准入权。新前缀仅一Human的另一个合法状态条件，不能授跨患者资格。\n'
  with f.open('a') as out:out.write(block)
 if frozen_new:
  marker2='## 冻结新前缀的绝对预测与配对差分'
  if marker2 not in f.read_text():
   lines=['\n'+marker2,'','模型和候选在新prefix前冻结，没有据新B/H150重新拟合或重选。绝对预测保留原H150锚点；配对差分另列，不能把事后重锚解释成原事前精度。','', '|候选|实际JF|名义绝对误差|学习绝对误差|冻结学习ΔJF|实际新H150配对ΔJF|原门|','|---|---:|---:|---:|---:|---:|---|']
   for row in frozen_new['rows']:
    ff=lambda x:'—' if x is None else f'{x:.6f}'
    lines.append('|'+row['id']+'|'+ '|'.join([ff(row['actual_JF']),ff(row['nominal_absolute_error']),ff(row['learned_absolute_error']),ff(row['frozen_learned_delta_vs_original_H150']),ff(row['actual_delta_vs_new_H150']),str(row['qualified'])])+'|')
   lines+=['','新prefix仍为同一Human且只一状态组；原始绝对成本漂移与动作差分收益分开判断。若新H150不合格，其差值仅为诊断，不授正式强父收益。']
   with f.open('a') as out:out.write('\n'.join(lines)+'\n')
 print('PROXY_VALIDATION_COMPLETED_WITH_SCOPE_LIMITS',flush=True)
if __name__=='__main__':main()
