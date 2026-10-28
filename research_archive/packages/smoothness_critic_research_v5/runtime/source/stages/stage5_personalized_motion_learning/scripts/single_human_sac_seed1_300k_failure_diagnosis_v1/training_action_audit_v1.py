from inventory_v1 import *
from audit_saved_v1 import stats
import csv, collections, shutil
def run():
    source=W/'single_human_sac_seed1_continuation/output_attempt3/SAC_SEED1_LEARNING_CURVE_COMBINED.csv'
    allrows=list(csv.DictReader(source.open()));groups={'random_initial_0_5k':[], 'early_learned_5k_50k':[], 'middle_50k_150k':[], 'late_150k_250k':[], 'final_250k_300k':[]}
    episodes={k:[] for k in groups};missing=[]
    for row in allrows:
        end=int(row['training_step']);path=R/row['action_evidence']
        if not path.exists():missing.append(str(path));continue
        with np.load(path) as z:
            raw=z['raw_action'];exe=z['executed_action'];accepted=np.isin(z['status'],['ACCEPTED','IDENTICAL_CONTINUATION'])
            ids=end-len(raw)+np.arange(len(raw))+1
            masks=[ids<=5000,(ids>5000)&(ids<=50000),(ids>50000)&(ids<=150000),(ids>150000)&(ids<=250000),ids>250000]
            for (name,group),mask in zip(groups.items(),masks):
                if np.any(mask):group.append((raw[mask],exe[mask],accepted[mask]))
        name='random_initial_0_5k' if end<=5000 else 'early_learned_5k_50k' if end<=50000 else 'middle_50k_150k' if end<=150000 else 'late_150k_250k' if end<=250000 else 'final_250k_300k'
        parts=json.loads(row.get('reward_totals') or row.get('reward_decomposition'))
        episodes[name].append(dict(step=end,duration_s=float(row['duration_s']),return_=float(row.get('reward_total') or row['episode_return']),reason=row['abort_reason'],reward_parts=parts,success=str(row.get('success') or row.get('causal_task_complete')).lower()=='true'))
    result={}
    for name,group in groups.items():
        raw=np.concatenate([g[0] for g in group]);exe=np.concatenate([g[1] for g in group]);accepted=np.concatenate([g[2] for g in group]);ep=episodes[name]
        result[name]=dict(action_count=len(raw),raw=stats(raw),executed=stats(exe),rejection_rate=float(np.mean(~accepted)),actual_target_modification_rate=float(np.mean(np.any(np.abs(exe-raw)>1e-5,axis=1))),mean_abs_target_discrepancy_deg=(np.mean(np.abs(exe-raw),axis=0)*62.5).tolist(),saturation_any_rate=float(np.mean(np.any(np.abs(raw)>=.95,axis=1))),episodes=len(ep),successful_episodes=sum(r['success'] for r in ep),episode_abort_reason_counts=dict(collections.Counter(r['reason'] for r in ep)),mean_duration_s=float(np.mean([r['duration_s'] for r in ep])),mean_return=float(np.mean([r['return_'] for r in ep])),mean_reward_parts={k:float(np.mean([r['reward_parts'][k] for r in ep])) for k in ('force','shaping','completion','failure','rejection')})
    save('TRAINING_ACTION_AND_REWARD_TREND.json',dict(groups=result,missing_action_archives=missing,source=str(source),source_sha256=sha(source),scope='completed episodes only; random-vs-learned transition IDs inferred from episode ending step and action count; ongoing final partial episode excluded'))
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps({k:{f:v[f] for f in ('action_count','rejection_rate','saturation_any_rate','episodes','successful_episodes','mean_duration_s','mean_return','episode_abort_reason_counts')} for k,v in result.items()}),flush=True)
if __name__=='__main__':run()
