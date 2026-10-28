"""Post-exposed-test query sensitivity. No fitting, model mutation or physics."""
from pathlib import Path
import os,sys,json,hashlib,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
from scipy.stats import spearmanr
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected=list((P/'models').glob('CRITIC_*'))+[P/'source/v5_cost_critic.py'];before={str(f.relative_to(P)):sha(f) for f in protected if f.is_file()};out=[]
for result_file in sorted((P/'analysis').glob('CRITIC_*_RESULTS.json')):
 result=json.loads(result_file.read_text());frozen=read('models/CRITIC_'+result['id']+'_FROZEN.json');cfg=read('experiments/CRITIC_'+result['id']+'.json')
 for test in result['results']:
  model=read(frozen['models'][test['phase']]['path']);names=model['feature_names'];stored=np.array(model['train_x']);scale=np.array(model['x_scale']);center=np.array(model['x_center']);constant=np.ptp(stored*scale,axis=0)<=1e-8;clock=constant&np.array([any(w in n.lower() for w in ['elapsed','remaining','time','age']) for n in names]);data={r['id']:r for r in read('models/'+test['group']+'_TAIL_LABELS.json') if abs(r['horizon_s']-cfg['horizon_s'])<1e-9};reported={r['id']:r for r in test['rows']}
  for variant,mask in [('ORIGINAL',np.zeros(len(names),bool)),('TRAIN_CONSTANT_CLOCK_MEAN_QUERY',clock),('TRAIN_CONSTANT_ALL_MEAN_QUERY',constant)]:
   rows=[]
   for ident,saved in reported.items():
    row=data[ident];index={n:k for k,n in enumerate(row['feature_names'])};x=np.array([row['features'][index[n]] for n in names]);query=(x-center)/scale;query[mask]=0.;predictions=[]
    for length,weights in zip(model['lengths'],model['weights']):
     k=np.exp(-np.mean((stored-query)**2,axis=1)/(2*length*length));predictions.append(np.array(model['target_center'])+np.array(model['target_scale'])*(k@np.array(weights)))
    pred=np.mean(predictions,axis=0);std=np.std(predictions,axis=0)
    if variant=='ORIGINAL':assert np.max(abs(pred-np.array([saved['predicted_tail_components'][n] for n in model['target_names']])))<1e-8,'ORIGINAL_REPLAY'
    rows.append(dict(id=ident,short_JF=row['labels']['short_JF'],predicted_tail_JF=float(pred[0]),predicted_tail_JM=float(pred[1]),predicted_motion_worst_ratio=float(pred[3]),predicted_total_JF=float(row['labels']['short_JF']+pred[0]),ensemble_std_JF=float(std[0]),nearest_training_RMS_distance=float(np.sqrt(np.min(np.mean((stored-query)**2,axis=1)))),actual_tail_JF=row['labels']['tail_JF'],actual_full_remaining_JF=row['labels']['full_remaining_JF'],actual_full_task_JF=saved['actual_full_task_JF'],actual_full_task_JM=saved['actual_full_task_JM'],actual_motion_worst_ratio=saved['actual_motion_worst_ratio'],actual_qualified=saved['qualified']))
   choice=min(rows,key=lambda r:r['predicted_total_JF']);actual=np.array([r['actual_tail_JF'] for r in rows]);pred=np.array([r['predicted_tail_JF'] for r in rows]);err=pred-actual;eligible=[r for r in rows if r['actual_qualified']];oracle=min(eligible,key=lambda r:r['actual_full_remaining_JF']);pairs=[(rows[i]['predicted_total_JF']-rows[j]['predicted_total_JF'])*(rows[i]['actual_full_remaining_JF']-rows[j]['actual_full_remaining_JF'])>0 for i in range(len(rows)) for j in range(i) if abs(rows[i]['actual_full_remaining_JF']-rows[j]['actual_full_remaining_JF'])>1e-10]
   out.append(dict(model=result['id'],phase=test['phase'],test_group=test['group'],variant=variant,training_constant_threshold_raw_peak_to_peak=1e-8,mean_imputed_features=[n for n,m in zip(names,mask) if m],unmasked_choice=choice['id'],choice_actual_qualified=choice['actual_qualified'],choice_predicted_motion_worst_ratio=choice['predicted_motion_worst_ratio'],choice_actual_motion_worst_ratio=choice['actual_motion_worst_ratio'],actual_chosen_full_JF=choice['actual_full_task_JF'],actual_chosen_full_JM=choice['actual_full_task_JM'],qualified_oracle=oracle['id'],qualified_choice_regret_N_s=choice['actual_full_remaining_JF']-oracle['actual_full_remaining_JF'] if choice['actual_qualified'] else None,tail_JF_RMSE=float(np.sqrt(np.mean(err**2))),within_menu_centered_tail_JF_RMSE=float(np.sqrt(np.mean((err-err.mean())**2))),mean_nearest_training_RMS_distance=float(np.mean([r['nearest_training_RMS_distance'] for r in rows])),pairwise_total_cost_order_accuracy=float(np.mean(pairs)),cost_spearman_all_complete_candidates=float(spearmanr([r['predicted_total_JF'] for r in rows],[r['actual_full_remaining_JF'] for r in rows]).statistic),rows=rows))
after={str(f.relative_to(P)):sha(f) for f in protected if f.is_file()};assert before==after,'ORIGINAL_FROZEN_ARTIFACT_CHANGED'
result=dict(status='POST_EXPOSED_DIAGNOSTIC_COMPLETE',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(P/'experiments/CRITIC_FEATURE_SENSITIVITY_PROTOCOL.json'),rows=out,original_frozen_artifacts_unchanged=True,protected_artifact_sha256=before,new_physical_START=0,new_native_steps=0,refitted_models=0,scope='Synthetic mean-imputation of test queries in training-near-constant coordinates only; original weights/training kernels unchanged. Same exposed test, not an independent validation, legal-state reconstruction or deployed controller. Future qualification/tail labels never mask the offered menu; only actual measured short cost and causal H features enter each choice. Primary frozen-model conclusions are unchanged.')
(P/'analysis/CRITIC_FEATURE_SENSITIVITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
md='# Critic训练常量字段敏感性（已暴露数据诊断）\n\nCONFIRMED：原模型、权重、配置、原test结果及训练kernel完全不修改。按训练数据raw峰峰值≤1e−8定义近恒定字段，将相应标准化查询值置零，分别只处理clock名字和处理所有近恒定字段。规则不按test标签选字段；这仍是test已暴露后的诊断，不能替代新的冻结验证。测得C_short保持原口径，未来资格不mask菜单。\n\n|模型|查询干预|字段数|无mask选择|实际原门|tail JF RMSE|去菜单共同误差RMSE|平均最近训练距离|合格选择regret N·s|\n|---|---|---|---|---|---|---|---|---|\n'
for r in out:
 regret='FAIL不排名' if r['qualified_choice_regret_N_s'] is None else f"{r['qualified_choice_regret_N_s']:.6f}"
 md+='|'+'|'.join([r['model'],r['variant'],str(len(r['mean_imputed_features'])),r['unmasked_choice'],'PASS' if r['choice_actual_qualified'] else 'FAIL',f"{r['tail_JF_RMSE']:.6f}",f"{r['within_menu_centered_tail_JF_RMSE']:.6f}",f"{r['mean_nearest_training_RMS_distance']:.6f}",regret])+'|\n'
md+='\nSUPPORTED：此干预可辨别近恒定字段对当前核距离、成本排序与预测误差的算法敏感性；它不能证明真实环境中唯一的物理因果误差来源。查询均值置换也不等于真实状态或合法任务时钟被改变。即使恢复一个合格选择，仍不证明独立于训练固定动作／1秒short的Learning增量、失败检测能力或真实尝试节省。未重训failure模型，已发生motion极值与缺失历史问题仍保留；泛化及修复模型的新盲验证NOT_TESTED。\n'
(P/'CRITIC_FEATURE_SENSITIVITY.md').write_text(md);print('CRITIC_FEATURE_SENSITIVITY',len(out),'rows; frozen artifacts unchanged')
