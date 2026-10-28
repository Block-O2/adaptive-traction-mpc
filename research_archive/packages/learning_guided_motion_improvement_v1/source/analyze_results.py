"""Post-run whole-trajectory analysis; no physics or model-driven new actions."""
from pathlib import Path
import os,sys,json,csv,hashlib,math
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
from scipy.stats import spearmanr
P=Path(__file__).resolve().parents[1];R=P/'runtime';sys.path.insert(0,str(P/'source'))
def load(n):return json.loads((P/n).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float):return x if math.isfinite(x) else None
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def summary_error(actual,pred,base):
 y=np.asarray(actual);p=np.asarray(pred);err=p-y;valid=np.abs(y-base)>1e-8
 return {'n_complete_trajectories':len(y),'MAE':float(np.mean(abs(err))) if len(y) else None,'RMSE':float(np.sqrt(np.mean(err*err))) if len(y) else None,'bias':float(np.mean(err)) if len(y) else None,'max_abs_error':float(np.max(abs(err))) if len(y) else None,'gain_sign_correct':int(np.sum(np.sign(base-y[valid])==np.sign(base-p[valid]))),'gain_sign_denominator':int(valid.sum()),'spearman':float(spearmanr(y,p).statistic) if len(y)>2 and np.ptp(y)>1e-12 and np.ptp(p)>1e-12 else None}
def best(rows):return min((r for r in rows if r.get('qualified')),key=lambda r:r['JF'],default=None)
def f(v,n=6):return '—' if v is None else f'{v:.{n}f}'

def main():
 results=load('THREE_ARM_RESULTS.json');base=results['baseline'];rows=results['rows'];primary={a:best(v[:12]) for a,v in rows.items()};overall={a:best(v) for a,v in rows.items()};metrics=[];errorstudy={};curves={}
 for arm,rr in rows.items():
  incumbent=base['JF'];curve=[]
  for n,r in enumerate(rr,1):
   if r.get('qualified'):incumbent=min(incumbent,r['JF'])
   curve.append({'attempt':n,'best_qualified_JF_including_parent':incumbent,'gain_N_s':base['JF']-incumbent,'id':r['id']})
   if r.get('complete'):
    m=load(r['metrics_path']);p=r['prediction'];nom=p['baseline_anchored_nominal'];actual=[r['JF'],r['JM'],r['worst_ratio']];metrics.append({'id':r['id'],'arm':arm,'x':r['x'],'qualified':r['qualified'],'actual':actual,'nominal':nom,'learned':p.get('learned_prediction'),'std':p.get('learned_std'),'phase_actual':{ph:m['phase_cost']['phases'][ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN']},'phase_nominal':p['nominal']['phase_JF'],'prediction_created_unix':p['created_unix'],'training_ids':p['training_attempt_ids']})
  curves[arm]=curve
  mm=[r for r in metrics if r['arm']==arm]
  errorstudy[arm]={'force_nominal_anchored':summary_error([r['actual'][0] for r in mm],[r['nominal'][0] for r in mm],base['JF']),'moment_nominal_anchored':summary_error([r['actual'][1] for r in mm],[r['nominal'][1] for r in mm],base['JM']),'nominal_actual_motion_prediction':'UNKNOWN; no pure-physics pass prediction'}
  if arm=='C':
   for j,label,anchor in [(0,'force',base['JF']),(1,'moment',base['JM']),(2,'motion_worst_ratio',base['worst_ratio'])]:
    errorstudy[arm][label+'_learned_prequential']=summary_error([r['actual'][j] for r in mm],[r['learned'][j] for r in mm],anchor)
    y=np.array([r['actual'][j] for r in mm]);mu=np.array([r['learned'][j] for r in mm]);sd=np.array([r['std'][j] for r in mm]);errorstudy[arm][label+'_empirical_95_interval_coverage']={'inside':int(np.sum(abs(mu-y)<=1.96*sd)),'n':len(mm),'caution':'empirical coverage only; no calibrated confidence guarantee from this small local GP'}
   predicted_pass=[r for r in rr if r['prediction'].get('predicted_original_motion_pass')]
   errorstudy[arm]['predicted_motion_pass_but_original_failed']=[r['id'] for r in predicted_pass if not r.get('qualified')]
   errorstudy[arm]['predicted_motion_pass_denominator']=len(predicted_pass)
 # Strict START-before-prediction / own-history audit independent of optimizer internals.
 starts={r['id']:r for r in map(json.loads,(R/'ATTEMPTS.jsonl').read_text().splitlines()) if r['event']=='START'};firewall=[]
 for arm,rr in rows.items():
  prior=[]
  for r in rr:
   p=r['prediction'];assert p['created_unix']<=starts[r['id']]['unix'],'PREDICTION_AFTER_START';assert p['training_attempt_ids']==prior,'FOREIGN_OR_FUTURE_FEEDBACK';prior.append(r['id'])
  firewall.append({'arm':arm,'attempts':len(rr),'own_prior_attempts_only':True})
 primary_best=min((r for r in primary.values() if r),key=lambda r:r['JF'],default=None);full_best=min((r for r in overall.values() if r),key=lambda r:r['JF'],default=None)
 convergence={}
 common=min(max(0,base['JF']-r['JF']) for r in primary.values() if r)
 targets=sorted(set([.01,.1,.25,.5,.75,1.,common]+[max(0.,base['JF']-r['JF']) for r in primary.values() if r]))
 for arm,curve in curves.items():
  convergence[arm]={str(target):next((r['attempt'] for r in curve if r['gain_N_s']>=target-1e-8),None) for target in targets}
 result={'baseline':base,'attempt_denominators':{a:len(r) for a,r in rows.items()},'complete_counts':{a:sum(r['complete'] for r in rr) for a,rr in rows.items()},'qualified_counts':{a:sum(r['qualified'] for r in rr) for a,rr in rows.items()},'primary_first12':primary,'best_all_assigned':overall,'best_primary12_id':None if primary_best is None else primary_best['id'],'best_all_id':None if full_best is None else full_best['id'],'C_better_than_A_B_at12':bool(primary['C'] and all(primary[a] and primary['C']['JF']<primary[a]['JF']-1e-7 for a in ['A','B'])),'C_better_than_A_B_all':bool(overall['C'] and all(overall[a] and overall['C']['JF']<overall[a]['JF']-1e-7 for a in ['A','B'])),'common_gain_at12_N_s':common,'attempts_to_gain':convergence,'incumbent_curves':curves,'prediction_error_study':errorstudy,'feedback_firewall':firewall,'scope':'one nominal Human, one optimization live parent; equal new physical attempts first12; historical prior and proxy/fit compute not equal-cost proof','whole_trajectory_prediction_rows':metrics}
 put('OPTIMIZATION_ANALYSIS.json',result);put('MODEL_RESIDUAL_RESULTS.json',{'error_study':errorstudy,'rows':metrics,'training_split':'prequential whole candidate; x/trajectory groups and single parent context','independent_state_validation':'FROZEN_NEW_PREFIX_RESULTS.json if executed','feedback_firewall':firewall,'no_time_step_split':True})
 with (P/'THREE_ARM_CANDIDATES.csv').open('w',newline='') as out:
  w=csv.writer(out);w.writerow(['arm','attempt','id','x_O','x_R','complete','qualified','JF_N_s','JM_Nm_s','qualified_gain_vs_H150_N_s','diagnostic_raw_JF_delta_vs_H150_N_s','worst_original_ratio','failed_requirements'])
  for arm,rr in rows.items():
   for n,r in enumerate(rr,1):w.writerow([arm,n,r['id'],*r['x'],r['complete'],r['qualified'],r.get('JF'),r.get('JM'),base['JF']-r['JF'] if r['qualified'] else None,r['JF']-base['JF'] if r['complete'] else None,r.get('worst_ratio'),r.get('motion_vs_B',{}).get('failed_requirements',r.get('error'))])
 lines=['# 强父与全部新候选比较','',f"共同H150强父完整JF={f(base['JF'])} N·s，JM={f(base['JM'])} Nm·s。原motion始终相对同链B，不按H150重新放松。主比较固定前12次；扩展单列。",'', '|臂|真实优化attempt|完整|原门合格|前12最佳JF|全分配最佳JF|全最佳相对H150降低%|','|---|---:|---:|---:|---:|---:|---:|']
 for arm in 'ABC':
  rr=rows[arm];q=overall[arm];lines.append(f"|{arm}|{len(rr)}|{sum(r['complete'] for r in rr)}|{sum(r['qualified'] for r in rr)}|{f(None if primary[arm] is None else primary[arm]['JF'])}|{f(None if q is None else q['JF'])}|{f(None if q is None else 100*(base['JF']-q['JF'])/base['JF'])}|")
 lines+=['','## 到达同等合格收益所需真实优化attempt','', '以下阈值是描述性成本对照，包含固定小收益阈值及每臂前12的最佳实际收益；不用于重新选择模型或修改接受门。未达到记为未达到，所有失败仍在attempt分母。','', '|完整JF降幅 N·s|A|B|C|','|---:|---:|---:|---:|']
 for target in targets:lines.append('|'+f(target)+'|'+ '|'.join(str(convergence[arm][str(target)]) if convergence[arm][str(target)] is not None else '未达到' for arm in 'ABC')+'|')
 lines+=['','## 新参数与实际执行','', 'x修改冻结18D differential系数[1,6]，Δ=(0.002*x_O,0.002*x_R)，其余H150结构固定。参数不是历史最佳动作编号。新参数仍由原planner/certificate/admission决定执行与拒绝；实际metadata见每个attempt_RESULT.json的free_parameter_execution和完整receipt。','', '|臂|最佳ID|x_O|x_R|JF降幅 N·s|JM变化 Nm·s|最差原门比|','|---|---|---:|---:|---:|---:|---:|']
 for arm,r in overall.items():
  if r:lines.append(f"|{arm}|{r['id']}|{f(r['x'][0])}|{f(r['x'][1])}|{f(base['JF']-r['JF'])}|{f(r['JM']-base['JM'])}|{f(r['worst_ratio'])}|")
 lines+=['','所有尝试原始行见THREE_ARM_CANDIDATES.csv；失败/partial不参与正式JF排名，但保留计算与START分母。完整对照、phase JF、motion和参数meta分别在attempts、runtime/reports与原raw中。','',f"C前12是否严格超过A/B：{result['C_better_than_A_B_at12']}；全分配是否严格超过：{result['C_better_than_A_B_all']}。这是本轮有限确定性开发比较，不是统计或患者总体排序。"]
 (P/'BASELINE_AND_CANDIDATE_COMPARISON.md').write_text('\n'.join(lines)+'\n')
 lines=['# 学习残差研究','', '输入为连续二维参数和公开的名义模型输出；相同父context记录但恒定，不能称学得患者状态条件映射。C采用固定length=.6的RBF GP，用自身已完成完整轨迹的JF/JM残差与原motion最差比反馈训练。没有大型神经网络、PPO或动作编号分类。', '', '原motion余量标签来自仿真评价器的native Human运动；当前患者部署所需可测运动合同尚未验证。它是离线仿真监督反馈，不是目标candidate未来真值输入。', '', '每次预测严格早于START，只使用自身先前attempt；没有按相邻时间步拆验证集。下表包含所有完整C候选，不能只挑成功轨迹。', '', '|输出|名义/基准预测RMSE|学习预序RMSE|学习MAE|95%区间经验覆盖|','|---|---:|---:|---:|---:|']
 for label,nomkey in [('force','force_nominal_anchored'),('moment','moment_nominal_anchored'),('motion_worst_ratio',None)]:
  st=errorstudy['C'][label+'_learned_prequential'];cov=errorstudy['C'][label+'_empirical_95_interval_coverage'];lines.append(f"|{label}|{f(errorstudy['C'][nomkey]['RMSE']) if nomkey else 'UNKNOWN physical margin'}|{f(st['RMSE'])}|{f(st['MAE'])}|{cov['inside']}/{cov['n']}|")
 lines +=['',f"预测motion可通过却实际原门未过的C候选：{errorstudy['C']['predicted_motion_pass_but_original_failed']}；分母{errorstudy['C']['predicted_motion_pass_denominator']}。完整预测/误差见MODEL_RESIDUAL_RESULTS.json。",'', '同状态预序误差改善不自动等于跨状态泛化或优化额外价值；C是否超过A/B由固定12次物理预算和冻结真实验证单独判定。GP不确定性只作有限局部探索约束，本轮没有校准保证。失败partial不产生伪完整force标签，触发后续trust region缩小。']
 (P/'MODEL_RESIDUAL_STUDY.md').write_text('\n'.join(lines)+'\n')
 # Standalone scientific figure, preserving all numerical exports.
 import matplotlib.pyplot as plt
 (P/'figures').mkdir(exist_ok=True)
 fig,axs=plt.subplots(1,3,figsize=(16,4.5),layout='constrained');colors={'A':'#2166ac','B':'#b35806','C':'#008837'}
 for arm,curve in curves.items():
  axs[0].plot([r['attempt'] for r in curve],[r['gain_N_s'] for r in curve],label=arm,color=colors[arm],marker='.',ms=4)
  for r in rows[arm]:
   if r.get('complete'):axs[1].scatter(r['JF']-base['JF'],r['JM']-base['JM'],c=colors[arm],marker='o' if r['qualified'] else 'x',s=22,alpha=.7)
 axs[0].axvline(12,color='.5',ls='--');axs[0].set(xlabel='New native attempts / arm',ylabel='Best qualified JF gain vs H150 [N s]');axs[0].legend(title='A direct / B physics / C residual')
 axs[1].axhline(0,c='.5',lw=.7);axs[1].axvline(0,c='.5',lw=.7);axs[1].set(xlabel='Actual JF change [N s]',ylabel='Actual JM change [Nm s]')
 mm=[r for r in metrics if r['arm']=='C'];axs[2].plot(range(1,len(mm)+1),[r['nominal'][0]-r['actual'][0] for r in mm],label='Nominal anchored',marker='.',c='#b35806');axs[2].plot(range(1,len(mm)+1),[r['learned'][0]-r['actual'][0] for r in mm],label='Residual prequential',marker='.',c='#008837');axs[2].axhline(0,c='.5',lw=.7);axs[2].set(xlabel='C attempt',ylabel='JF prediction error [N s]');axs[2].legend()
 for ax in axs:ax.grid(alpha=.2)
 fig.suptitle('Single nominal Human, one live parent | original task / safety / motion gates')
 fig.savefig(P/'figures/THREE_ARM_COMPARISON.png',dpi=180);fig.savefig(P/'figures/THREE_ARM_COMPARISON.svg');plt.close(fig)
 print(json.dumps(clean({'primary':{a:None if r is None else {'id':r['id'],'JF':r['JF']} for a,r in primary.items()},'overall':{a:None if r is None else {'id':r['id'],'JF':r['JF']} for a,r in overall.items()},'C_better12':result['C_better_than_A_B_at12']})),flush=True)
if __name__=='__main__':main()
