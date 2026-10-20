"""Preserve a frozen baseline qualification failure; do not resume physics."""
from pathlib import Path
import json,time,math,numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
stop=read('PHYSICS_STOP.json');assert stop['reason']=='T_MOTION_BASELINE_FAIL',stop
selection=read('FROZEN_SELECTION.json');group='W1';rr=read(group+'_RESULTS.json')['rows'];t=next(r for r in rr if r['candidate']['id']=='T');b=next(r for r in rr if r['candidate']['id']=='B')
assert not t['motion']['acceptance_pass']
assert not any(r['candidate']['id']==selection['primary']['id'] for r in rr)
ident=t['id'];bm=read('reports/'+b['id']+'_MEASURED.json');tm=read('reports/'+ident+'_MEASURED.json');su=read('source/results/'+ident+'/summary.json');z=np.load(P/'motion_series'/(ident+'.npz'));nt=z['time_s'];phase=z['phase'];signals={'velocity_deg_s':np.rad2deg(z['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(z['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(z['jerk_rad_s3'])}
counts={};first=None
for lr in su['learning_records']:
 d=su['decisions'][lr['decision_index']];ph=d['phase'];slot=counts.get(ph,0);counts[ph]=slot+1
 if ph=='RETURN' and slot==2:first=d;break
assert first is not None
cut=first['decision_request_time_s'];pre=nt<=cut+1e-9;protocol=read('MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];max_duration=bm['dose']['duration_s']+protocol['total_duration_abs_delta_s'];max_n=math.floor(max_duration/.00025)+1
details=[]
for req in t['motion']['failed_requirements']:
 if '/' not in req:continue
 sig,met=req.split('/');a=np.array(tm['motion']['raw']['full'][sig][met]);base=np.array(bm['motion']['raw']['full'][sig][met]);x=signals[sig]
 for j,joint in enumerate(['hip','knee']):
  if a[j]<=base[j]*protocol['burden_ratio']+1e-7:continue
  threshold=base[j]*protocol['burden_ratio']+1e-7;peak=int(np.argmax(abs(x[:,j])));before_count=int(np.sum(abs(x[pre,j])>threshold));all_count=int(np.sum(abs(x[:,j])>threshold));byphase={ph:dict(samples_over_full_B_limit=int(np.sum((phase==ph)&(abs(x[:,j])>threshold))),max_abs=float(abs(x[phase==ph,j]).max()),metric=tm['motion']['raw']['phases'][ph][sig][met][j]) for ph in ['OUTBOUND','HOLD','RETURN']}
  details.append(dict(requirement=req,joint=joint,T=float(a[j]),B=float(base[j]),ratio=float(a[j]/base[j]),limit_ratio=protocol['burden_ratio'],by_phase=byphase,peak_task_s=float(nt[peak]-nt[0]),pre_first_candidate_samples_over_limit=before_count,all_samples_over_limit=all_count,maximum_samples_with_original_duration_tolerance=max_n,p95_prefix_irreversible_bound=bool(met=='p95_abs' and before_count>math.ceil(.05*max_n)),interpretation='Phase localization is descriptive. Only the stated lower-bound flag proves that a later RETURN2/3-only action cannot repair this particular whole-task percentile under the original timing gate.'))
q=z['true_q_rad'];pre_exc=np.rad2deg(np.ptp(q[pre],axis=0));b_exc=np.array(bm['dose']['excursion_deg']);exc_bound=(pre_exc>b_exc+protocol['excursion_abs_delta_deg']+1e-7).tolist()
out=dict(status='FROZEN_BASELINE_MOTION_FAIL',group=group,failed_requirements=t['motion']['failed_requirements'],details=details,first_planned_D_request_physical_s=cut,first_planned_D_request_task_s=cut-nt[0],prefix_excursion_lower_bound_deg=pre_exc.tolist(),matched_B_full_excursion_deg=b_exc.tolist(),prefix_excursion_irreversible_upper_failure=exc_bound,full_T_excursion_deg=tm['dose']['excursion_deg'],task=t['task'],safety=t['absolute_safety'],receipt=t['receipt'],force_gain_vs_B_percent=t['motion']['gain_percent'],primary_not_reselected=True,new_candidate_not_executed_in_W1=True,reason_for_no_more_physics='Frozen execution harness prospectively gates D on qualified T. Do not alter the gate/code or choose a different primary after seeing validation. W2 remains a frozen but unstarted condition.',not_established='This is a T domain failure, not a physical failure result for the unexecuted D; later-action repair is ruled out only where the explicit prefix lower bound succeeds.')
(P/'audit/VALIDATION_BASELINE_FAILURE_DIAGNOSIS.json').write_text(json.dumps(out,indent=2)+'\n')
validation=dict(status='BLOCKED_BY_FROZEN_BASELINE_MOTION_GATE',primary=selection['primary'],source_id=selection['source_id'],planned_new_conditions=2,attempted_new_conditions=1,new_candidate_conditions_executed=0,new_candidate_conditions_qualified=0,development_deterministic_repeat='PASS',baseline_W1_rows=rr,stop=stop,diagnosis='audit/VALIDATION_BASELINE_FAILURE_DIAGNOSIS.json',W2='NOT_STARTED_PER_FROZEN_STOP_GATE',selection_unchanged_after_validation=True,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',same_Human_only=True,conclusion='Development small-force candidate and deterministic repeats remain valid. Independent new-prefix candidate qualification is not established; no promotion to a broader baseline.')
(P/'VALIDATION_RESULTS.json').write_text(json.dumps(validation,indent=2)+'\n')
lines=['# 扩展状态motion失败：冻结停止门诊断','','W1的完整B/18D/T已实际执行。T在原motion门失败，原task、绝对安全和causal执行仍通过。冻结harness要求T先合格才运行新D，因此D未在W1启动；W2按同一停止门未启动。不修改验证代码、不降低门槛，也不按失败结果换primary。','',f"失败项：{t['motion']['failed_requirements']}。匹配T仍保留降力{t['motion']['gain_percent']:.6f}%，低力不替代motion资格。",'', '逐joint/full/phase指标、超全程B限的样本数和不可逆prefix下界见audit/VALIDATION_BASELINE_FAILURE_DIAGNOSIS.json。phase近零比值不当作主要失败机制。若已完成的prefix自身超过全程允许excursion，或已超过固定任务可容许的5%高值样本计数，则更晚的RETURN2/3动作不能消除已经发生的负担；仅在JSON明确下界成立的项作此结论。其余项不作不可修复断言。','', '这暴露了T末段时间修复的适用域边界：末段变缓不能自动约束整条状态相关轨迹的p95/剂量。它不是未执行D的负物理结果；也不排除未来预注册修复研究。下一步优先扩大合法状态与motion准入机制验证，而不是把本轮小幅降力方案升级为通用基线。','', '本轮执行门未变，全部失败与partial父计算均入账；不因预算仍充足而绕过冻结停止门追加物理。']
(P/'VALIDATION_FAILURE_DIAGNOSIS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(out),flush=True)
