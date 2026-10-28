"""Frozen diagnostic of raw-target versus bounded log-excess motion GP."""
import json,time
import numpy as np
from acl2_shared import P,read,put,sha,utc,decision
MODEL='models/STRUCTURAL_MOTION_DIAGNOSTIC/model.json'
PRED='predictions/STRUCTURAL_MOTION_DIAGNOSTIC.json'
LOCK='audit/STRUCTURAL_MOTION_DIAGNOSTIC_LOCK.json'

def kernel(x,X,length):return np.exp(-np.sum((x[:,None,:]-X[None,:,:])**2,axis=2)/(2*length*length))

def build():
    assert not (P/'VALIDATION_INPUT_LOCK.json').exists(),'HELDOUT_ALREADY_OPEN'
    assert not (P/LOCK).exists(),'DIAGNOSTIC_ALREADY_LOCKED'
    prereg=read('STRUCTURAL_MOTION_DIAGNOSTIC_PREREGISTRATION.json');original=read(prereg['original_gp_path']);assert sha(P/prereg['original_gp_path'])==prereg['original_gp_sha256']
    ids=prereg['exact_same_training_attempt_ids'];training=[read('attempts/'+i+'_RESULT.json') for i in ids];base=training[0];X=np.asarray(original['x']);y=np.asarray([r['worst_ratio'] for r in training]);floor=float(np.sqrt(.95/1.05))
    assert len(ids)==len(X) and all(r['complete'] for r in training)
    assert np.allclose(X,[r['action'].get('x',[0.]*8) for r in training],atol=1e-12)
    assert np.allclose(y-base['worst_ratio'],np.asarray(original['y'])[:,2],atol=1e-12),'TRAINING_DATA_MISMATCH'
    assert float(y.min())>=floor-1e-12,'TARGET_BOUND_INCONSISTENT'
    z=np.log(np.maximum(y-floor,1e-12));center=float(z[0]);scale=max(float(np.std(z-center)),.06);L=np.asarray(original['L']);alpha=np.linalg.solve(L.T,np.linalg.solve(L,(z-center)/scale))
    model=dict(utc=utc(),x=X,L=L,length=original['length'],alpha=alpha,center_z=center,scale_z=scale,structural_floor=floor,training_attempt_ids=ids,training_raw_worst_ratio=y,training_transformed_z=z,source_sha256=sha(__file__),original_model_path=prereg['original_gp_path'],original_model_sha256=prereg['original_gp_sha256'],same_original_covariance_used=True,physical_attempts_added=0)
    put(MODEL,model)
    points=np.random.default_rng(2026102501).uniform(-.65,.65,(6,8));K=kernel(points,X,original['length']);V=np.linalg.solve(L,K.T);variance=np.maximum(1e-10,1-np.sum(V*V,axis=0));mean_z=center+K@alpha*scale;sd_z=np.sqrt(variance)*scale
    oldmean=base['worst_ratio']+(K@np.asarray(original['alpha'])*np.asarray(original['scale']))[:,2];oldsd=np.sqrt(variance)*np.asarray(original['scale'])[2]
    predictions=[]
    for i,x in enumerate(points):
        mu=float(mean_z[i]);s=float(sd_z[i]);bounded=dict(mean=floor+float(np.exp(mu+.5*s*s)),lower95=floor+float(np.exp(mu-1.96*s)),upper95=floor+float(np.exp(mu+1.96*s)),one_sigma_upper=floor+float(np.exp(mu+s)),latent_mean=mu,latent_sd=s)
        raw=dict(mean=float(oldmean[i]),lower95=float(oldmean[i]-1.96*oldsd[i]),upper95=float(oldmean[i]+1.96*oldsd[i]),one_sigma_upper=float(oldmean[i]+oldsd[i]),sd=float(oldsd[i]))
        predictions.append(dict(id='LOCKED_REPEAT_FAILURE_DOMAIN_%02d'%(i+1),x=x,original_raw_GP=raw,bounded_log_excess_GP=bounded))
    put(PRED,dict(utc=utc(),predictions=predictions,seed=2026102501,source_sha256=sha(__file__),model_sha256=sha(P/MODEL),no_test_outcomes_used=True))
    trainhash={'attempts/'+i+'_RESULT.json':sha(P/'attempts'/(i+'_RESULT.json')) for i in ids}
    lock=dict(utc=utc(),files={MODEL:sha(P/MODEL),PRED:sha(P/PRED),'source/acl2_structural_motion.py':sha(__file__),'STRUCTURAL_MOTION_DIAGNOSTIC_PREREGISTRATION.json':sha(P/'STRUCTURAL_MOTION_DIAGNOSTIC_PREREGISTRATION.json'),prereg['original_gp_path']:sha(P/prereg['original_gp_path'])},training_result_sha256=trainhash,training_attempt_ids=ids,heldout_physics_not_opened=True,no_candidate_selection_feedback=True,physical_attempts_added=0)
    put(LOCK,lock);print('STRUCTURAL_MOTION_BUILT',len(ids),'training rows,6frozen predictions,0native',flush=True)

def evaluate():
    if not (P/LOCK).exists():return
    lock=read(LOCK);errors=[]
    for name,expected in {**lock['files'],**lock['training_result_sha256']}.items():
        if not (P/name).exists() or sha(P/name)!=expected:errors.append('LOCK_HASH:'+name)
    predictions=read(PRED)['predictions'];model=read(MODEL);floor=model['structural_floor'];data=[]
    for pred in predictions:
        result=P/'attempts'/(pred['id']+'_RESULT.json')
        if not result.exists():continue
        actual=json.loads(result.read_text());row=dict(id=pred['id'],complete=actual['complete'],qualified=actual['qualified'],actual_worst_ratio=actual.get('worst_ratio'),original_raw_GP=pred['original_raw_GP'],bounded_log_excess_GP=pred['bounded_log_excess_GP'])
        if not np.allclose(actual['action']['x'],pred['x'],atol=1e-12):errors.append('TEST_ACTION_MISMATCH:'+pred['id'])
        if actual.get('prediction'):
            p=actual['prediction']
            if abs(p['predicted_outcome'][2]-pred['original_raw_GP']['mean'])>1e-10 or abs(p['predicted_sd'][2]-pred['original_raw_GP']['sd'])>1e-10:errors.append('ORIGINAL_FROZEN_PREDICTION_MISMATCH:'+pred['id'])
        data.append(row)
    metrics={}
    for name in ['original_raw_GP','bounded_log_excess_GP']:
        full=[r for r in data if r['complete']];error=np.asarray([r[name]['mean']-r['actual_worst_ratio'] for r in full])
        metrics[name]=dict(complete_defined_cases=len(full),RMSE=float(np.sqrt(np.mean(error*error))) if full else None,empirical95_coverage=float(np.mean([r[name]['lower95']<=r['actual_worst_ratio']<=r[name]['upper95'] for r in full])) if full else None,mean95_interval_width=float(np.mean([r[name]['upper95']-r[name]['lower95'] for r in full])) if full else None,screen_passes=[r['id'] for r in data if r[name]['one_sigma_upper']<=1],screen_false_passes=[r['id'] for r in data if r[name]['one_sigma_upper']<=1 and not r['qualified']],screen_false_rejects=[r['id'] for r in data if r[name]['one_sigma_upper']>1 and r['qualified']],predicted_means_below_structural_floor=sum(r[name]['mean']<floor-1e-12 for r in data))
    out=dict(utc=utc(),status='FAIL_LOCK_OR_IDENTITY' if errors else 'EXECUTED_FROZEN_DIAGNOSTIC' if len(data)==6 else 'PARTIAL_FROZEN_DIAGNOSTIC' if data else 'NOT_RUN',errors=errors,completed_test_rows=len(data),all_registered_test_cases=6,training_tasks=len(lock['training_attempt_ids']),same_original_training_data_kernel=True,structural_floor=floor,metrics=metrics,rows=data,raw_input_sha256={'attempts/'+r['id']+'_RESULT.json':sha(P/'attempts'/(r['id']+'_RESULT.json')) for r in data},physical_attempts_added=0,lock_sha256=sha(P/LOCK),source_sha256=sha(__file__),limitation='Same6 independently pre-registered simulation points, single fixed context. This checks prediction structure and screening tradeoffs only; the bounded model did not choose any primary or validation action, and intervals are not calibrated safety guarantees.')
    put('STRUCTURAL_MOTION_DIAGNOSTIC_RESULTS.json',out)
    text=['# 运动指标结构约束的冻结诊断','','此分支没有新增物理尝试，没有改变主GP、候选、PPO或原门。它使用原最终开发GP完全相同的32条训练记录（强固定+31个C候选）、相同核及协方差；只把目标改为 `log(worst_ratio-sqrt(.95/1.05))`。单一变体在6个已登记失败域点打开前冻结，无超参数搜索。','','数学下界由原累计行程两侧项决定。有界输出必然满足该下界，但这不证明它能预测低层非光滑反馈冲击，也不证明区间已校准。原Gaussian模型的mean+sd与变换模型的潜在Gaussian一倍sd上分位数均作既定启发式筛选，阈值仍为1；后者并非把lognormal均值和标准差直接当Gaussian区间。','','实际状态：'+out['status']+'；新测试结果 '+str(len(data))+'/6。','', '|模型|完整成本案例|worst_ratio RMSE|95%经验覆盖|平均区间宽度|筛选误放数|误拒数|低于结构下界mean数|','|---|---|---|---|---|---|---|---|']
    for name,m in metrics.items():text.append('|'+ '|'.join(str(v) for v in [name,m['complete_defined_cases'],m['RMSE'],m['empirical95_coverage'],m['mean95_interval_width'],len(m['screen_false_passes']),len(m['screen_false_rejects']),m['predicted_means_below_structural_floor']])+'|')
    text+=['','误放与误拒一起保留，避免以拒绝所有候选制造“筛选有效”的结论。6点结果仅是本固定上下文的诊断，不能升级为一般校准、安全保证或实际优化优势。详见 `STRUCTURAL_MOTION_DIAGNOSTIC_RESULTS.json` 和 `audit/STRUCTURAL_MOTION_DIAGNOSTIC_LOCK.json`。']
    (P/'STRUCTURAL_MOTION_DIAGNOSTIC.md').write_text('\n'.join(text)+'\n');print('STRUCTURAL_MOTION_EVALUATED',out['status'],len(data),flush=True)

if __name__=='__main__':
    import sys
    build() if len(sys.argv)>1 and sys.argv[1]=='build' else evaluate()
