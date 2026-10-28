"""Posthoc PPO exploration/credit diagnosis; never used to choose training actions."""
import json, hashlib, collections
import numpy as np
from acl2_shared import P,R,put,read,utc

def fingerprint(ident):
    f=R/'source/results'/ident/'trace.npz'
    if not f.exists():return None
    with np.load(f) as z:
        task=z['stage']=='TASK'
        arrays=[z[k][task] for k in ['reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2']]
    h=hashlib.sha256()
    for a in arrays:h.update(str(a.shape).encode());h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()

def main():
    rows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()]
    train=[r for r in rows if r['id'].startswith('PPO_SCRATCH_TRAIN_')]
    if not train:
        result=dict(status='NOT_RUN',utc=utc(),native_steps=0)
        put('PPO_EXECUTION_AND_SIGNAL_DIAGNOSIS.json',result);return result
    strong=next(r for r in rows if r['id']=='PPO_SCRATCH_STRONG');basehash=fingerprint(strong['id'])
    rolloutfile=P/'jobs/PPO_SCRATCH/RL_ROLLOUTS.jsonl'
    rollout=[json.loads(s) for s in rolloutfile.read_text().splitlines()] if rolloutfile.exists() else []
    rd={r['id']:r for r in rollout};items=[];qualified=[r for r in train if r['qualified']]
    for r in train:
        counts=collections.Counter();reasons=collections.Counter();phasecounts=collections.Counter()
        for e in r.get('execution',[]):
            m=e.get('modal')
            if not m:continue
            counts[m['status']]+=1;phasecounts[m['phase']+'/'+m['status']]+=1
            if m['status']=='ACCEPTED' and e.get('activated'):counts['ACCEPTED_AND_ACTIVATED']+=1
            if m.get('reason'):reasons[m['reason']]+=1
        rawhash=fingerprint(r['id']) if r['complete'] else None
        items.append(dict(id=r['id'],generation=(r.get('prediction') or {}).get('generation'),complete=r['complete'],qualified=r['qualified'],JF=r.get('JF'),JM=r.get('JM'),x=r['action']['x'],reward=(rd.get(r['id']) or {}).get('reward'),reference_sha256=rawhash,exact_reference_repeat_of_strong=rawhash==basehash if rawhash else None,modal_slot_counts=dict(counts),phase_modal_slot_counts=dict(phasecounts),rejection_reasons=dict(reasons),full_cost_undefined=not r['complete']))
    pairerrors=[]
    for i,a in enumerate(qualified):
        for b in qualified[:i]:
            if a['id'] not in rd or b['id'] not in rd:continue
            force=a['JF']-b['JF'];reward=rd[a['id']]['reward']-rd[b['id']]['reward']
            if abs(force)>1e-8 and force*reward>=0:pairerrors.append([a['id'],b['id']])
    generations=[]
    for f in sorted((P/'models/PPO_SCRATCH').glob('*_AFTER.json')):
        a=json.loads(f.read_text());u=a['update'];rewards=np.asarray(u['reward']);norm=(rewards-rewards.mean())/(rewards.std()+1e-8)
        before=json.loads(f.with_name(f.name.replace('_AFTER','_BEFORE')).read_text());oldmu=np.asarray(before['mu']);oldls=np.asarray(before['log_std']);z=np.asarray(before['sampled_pre_tanh_z']);initial_score_gradient=np.mean(norm[:,None]*(z-oldmu)/np.exp(2*oldls),axis=0);step=np.asarray(a['mu'])-oldmu
        actual=[r for r in train if (r.get('prediction') or {}).get('generation')==a['generation']]
        generations.append(dict(generation=a['generation'],episodes=len(rewards),complete=sum(r['complete'] for r in actual),qualified=sum(r['qualified'] for r in actual),reward_min=float(rewards.min()),reward_max=float(rewards.max()),reward_std=float(rewards.std()),reward_saturation_count=int(np.sum(abs(rewards)>4.95)),tanh_mu=np.tanh(a['mu']),std=np.exp(a['log_std']),policy_epochs=len(u['epochs']),last_exact_KL=u['epochs'][-1].get('exact_Gaussian_KL_after_update'),last_empirical_KL=u['epochs'][-1]['approx_KL_after_update'],critic_cancellation_max_error=float(np.max(abs(norm-np.asarray(u['advantage_normalized'])))),actor_step_dot_initial_score_gradient=float(step@initial_score_gradient),caution='Initial score-gradient alignment is descriptive; later clipped epochs/Adam momentum need not follow this single vector.'))
    totals=collections.Counter(k for r in items for k,v in r['modal_slot_counts'].items() for _ in range(v))
    permissions={}
    for phase,dimension in [('OUTBOUND',4),('RETURN',5)]:
        for sign,label in [(False,'nonpositive'),(True,'positive')]:
            chosen=[r for r in items if (r['x'][dimension]>0)==sign];accepted=sum(r['phase_modal_slot_counts'].get(phase+'/ACCEPTED',0) for r in chosen);rejected=sum(r['phase_modal_slot_counts'].get(phase+'/REJECTED',0) for r in chosen)
            permissions[phase+'/'+label]=dict(samples=len(chosen),accepted_slots=accepted,rejected_slots=rejected,accepted_fraction=accepted/max(1,accepted+rejected))
    result=dict(status='OBSERVED_ACTUAL_ROLLOUTS',utc=utc(),training_attempts=len(train),completed_task_count=sum(r['complete'] for r in train),qualified_count=len(qualified),rollout_records=len(rollout),execution_permissions_by_local_timing_sign=permissions,nonqualified_full_tasks_with_lower_JF_than_public_strong=[r['id'] for r in train if r['complete'] and not r['qualified'] and r['JF']<strong['JF']],unique_completed_actual_reference_profiles=len({r['reference_sha256'] for r in items if r['reference_sha256']}),exact_strong_reference_repeats=sum(r['exact_reference_repeat_of_strong'] is True for r in items),slot_counts=dict(totals),qualified_reward_order_mismatches=pairerrors,critic_role='For one constant context and one RL decision per episode, subtracting a common scalar value then centering advantages cancels that scalar exactly. Critic updates do not create state-dependent actor ranking here.',generations=generations,rows=items,scope='Posthoc diagnosis only; timing-sign acceptance is conditional on the actual joint-action samples/context, not a universal feasibility theorem. Not a policy input, additional native test, independent patient sample, or proof of good-region probability.')
    put('PPO_EXECUTION_AND_SIGNAL_DIAGNOSIS.json',result);return result

if __name__=='__main__':main()
