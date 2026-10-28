"""Measured parent/child comparison only, no reward revision or new physics."""
from common import ROOT,put
from pathlib import Path
import json,time,hashlib
import numpy as np

def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def main():
 if not (ROOT/'STAGE2_FROZEN.json').exists():
  if (ROOT/'STAGE2_RESULTS.json').exists() and read(ROOT/'STAGE2_RESULTS.json')['status']=='NOT_RUN':print('NOT_RUN');return
  raise RuntimeError('STAGE2_GATE_DECISION_REQUIRED')
 from replication_analysis import summarize
 summarize();frozen=read(ROOT/'STAGE2_FROZEN.json');stage1=read(ROOT/'STAGE1_COMPLETE.json');seed=frozen['seed'];ev=lines(ROOT/'ALL_EVALUATION_LOG.jsonl');training=[x for x in lines(ROOT/'ALL_TRAINING_LOG.jsonl') if x['stage']=='stage2'];metric=read(ROOT/'audit/ALL_SCIENTIFIC_METRICS.json')['episodes'];lookup={x['run']:x for x in metric};parents=[x for x in ev if x['training_seed']==seed and x['stage']=='stage1' and x['kind'] in [f"checkpoint{stage1['target']:03d}_first",f"checkpoint{stage1['target']:03d}_repeat"]];children=[x for x in ev if x['training_seed']==seed and x['stage']=='stage2'];done=read(ROOT/'STAGE2_COMPLETE.json') if (ROOT/'STAGE2_COMPLETE.json').exists() else {'status':'PARTIAL_INFRASTRUCTURE'}
 def average(rows,key):return float(np.mean([x[key] for x in rows])) if rows else None
 task_preserved=len(parents)==2 and len(children)==2 and all(x['success'] for x in parents+children);duration_preserved=task_preserved and all(abs(x['task_s']-19.03)<.05 for x in parents+children);pair_duration_equal=task_preserved and abs(average(children,'task_s')-average(parents,'task_s'))<1e-6
 parentJF=average(parents,'JF');childJF=average(children,'JF');parentJM=average(parents,'JM');childJM=average(children,'JM');force_reduced=bool(pair_duration_equal and childJF<parentJF);moment_change=(childJM/parentJM-1)*100 if childJM is not None and parentJM else None
 conclusion='FAILED_TASK_PRESERVATION' if not task_preserved else 'FAILED_PAIR_DURATION_COMPARABILITY' if not pair_duration_equal else 'DEVELOPMENT_EQUAL_DURATION_FORCE_REDUCTION_NOT_QUALIFIED' if force_reduced else 'NO_FORCE_REDUCTION_OBSERVED'
 if force_reduced and moment_change>0:conclusion+='; FORCE_MOMENT_TRADEOFF'
 if not duration_preserved:conclusion+='; ORIGINAL_19_030_NECESSARY_TIMING_NOT_PASSED'
 comparisons=[]
 for name,rows in [('Stage1 parent',parents),('Stage2 child',children)]:
  for row in rows:comparisons.append({'label':name,'kind':row['kind'],'row':row,'scientific_metrics':lookup[row['run']]})
 result={'unix':time.time(),'status':done['status'],'reason':conclusion,'conclusion':conclusion,'identity':'TASK_PRETRAINED_PPO_FINETUNING','seed':seed,'parent_checkpoint':frozen['parent_checkpoint'],'reward':frozen['reward'],'frozen_reward_config_sha256':hashlib.sha256((ROOT/'STAGE2_FROZEN.json').read_bytes()).hexdigest(),'training_episodes':len(training),'training_successes':sum(x['success'] for x in training),'RL_decisions':sum(x['decisions'] for x in training),'native_steps':sum(x['native_steps'] for x in training),'gradient_updates':sum(len(x['gradient_steps']) for x in training),'parent_runtime_successes':sum(x['success'] for x in parents),'parent_evaluation_attempts':len(parents),'child_runtime_successes':sum(x['success'] for x in children),'child_evaluation_attempts':len(children),'task_completion_preserved':task_preserved,'task_completion_sacrificed':not task_preserved,'necessary_duration_preserved':duration_preserved,'paired_runtime_duration_equal':pair_duration_equal,'parent_mean_TASK_s':average(parents,'task_s'),'child_mean_TASK_s':average(children,'task_s'),'parent_complete_JF':parentJF,'child_JF_full_only_if_task_complete':childJF,'parent_complete_JM':parentJM,'child_JM_full_only_if_task_complete':childJM,'JF_change_pct':(childJF/parentJF-1)*100 if childJF is not None and parentJF else None,'JM_change_pct':moment_change,'complete_force_reduction_observed':force_reduced,'formal_qualified_improvement':False,'reason_not_qualified':'Original B/H150 complete scorer and G4 strict qualification unavailable; native jerk/tracking/overshoot reported without invented motion thresholds.','paired_evaluations':comparisons,'no_reward_revision_or_final_test_tuning':True,'same_nominal_patient_initial_state_not_unseen_generalization':True}
 put(ROOT/'STAGE2_RESULTS.json',result)
 rows=['# Stage2性能优化研究','','身份：**TASK_PRETRAINED_PPO_FINETUNING**，不是scratch PPO。父checkpoint：`'+frozen['parent_checkpoint']+'`。选择规则在训练前固定为最小数值seed，不按力指标挑父策略。','','状态：'+done['status']+'；结论：'+conclusion+'。','','原任务/保护/物理不变；reward先冻结后训练：progress=5、completion=20、failure base=-10、force=1×JF/100、variation=.05×原归一化加速度平方积分；失败成本下限61.5，γ=1，硬安全独立。没有reward修订分支。Stage2配置SHA：`'+result['frozen_reward_config_sha256']+'`。继承PilotEnv通用metadata中的v3标记由stage2_reward_contract与public_reward_contract明确覆盖，actual reward独立重算按Stage2权重/失败下限执行；没有隐藏混用。','','训练'+str(len(training))+'集，成功'+str(result['training_successes'])+'次，'+str(result['RL_decisions'])+'个RL decisions、'+str(result['native_steps'])+'个native steps、'+str(result['gradient_updates'])+'次Adam更新。每10集核对任务成功率，若低于父last20即停止（比原协议>20个百分点更严格）。','','父/子冻结完成率：'+str(result['parent_runtime_successes'])+'/'+str(len(parents))+' → '+str(result['child_runtime_successes'])+'/'+str(len(children))+'；任务保持='+str(task_preserved)+'；19.030必要时长保持='+str(duration_preserved)+'；父子TASK时长相等='+str(pair_duration_equal)+'。失败partial积分不得作为完整收益。','','|策略/attempt|TASK s|runtime|JF|JM|tracking RMS °|5ms jerk RMS °/s³|','|---|---:|---|---:|---:|---|---|']
 for x in comparisons:
  row=x['row'];m=x['scientific_metrics'];native=m['native_motion'];rows.append(f"|{x['label']}/{x['kind']}|{row['task_s']:.3f}|{row['status']}|{row['JF']:.3f}|{row['JM']:.3f}|{m['tracking_rms_deg']}|{native['jerk_5ms_rms_deg_s3'] if native else 'N/A'}|")
 rows+=['','JF变化='+str(result['JF_change_pct'])+'%；JM变化='+str(result['JM_change_pct'])+'%。force下降但moment上升必须作为权衡，不能称完整改进。实际velocity/acceleration/native和5ms jerk、tracking、terminal error/overshoot、excursion、native torque receipt与source-age见STAGE2_RESULTS.json完整父子数值和评价raw。','','原B/H150完整motion/fairness/scorer和G4未闭合，本研究始终为不晋级开发实验。无论reward是否改善，FULL_QUALIFIED和正式性能优势均未授予。最终训练没有启动。']
 (ROOT/'STAGE2_PERFORMANCE_STUDY.md').write_text('\n'.join(rows)+'\n')
 identities=[]
 for p in (ROOT/'seeds'/str(seed)/'stage2/checkpoints').glob('*.json'):
  x=read(p);identities.append({'checkpoint':str(p.with_suffix('').relative_to(ROOT)),'model_sha256':x['model_sha256'],'policy_sha256':x['policy_sha256'],'reward_config_sha256':result['frozen_reward_config_sha256'],'identity':'TASK_PRETRAINED_PPO_FINETUNING'})
 put(ROOT/'STAGE2_CHECKPOINT_IDENTITY.json',{'config_sha256':result['frozen_reward_config_sha256'],'checkpoints':identities})
 print(json.dumps({'status':result['status'],'conclusion':conclusion,'training_episodes':len(training)}))
if __name__=='__main__':main()
