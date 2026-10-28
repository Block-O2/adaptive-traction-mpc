"""Finite evidence-gated queue. No unbounded search and no formal campaign."""
from pathlib import Path
import json,os,sys,time,traceback
from research_common import ROOT,RUNTIME,HARD_STOP,NO_TRAIN,atomic,append,read,decision,now,check_resources,pid_identity,sha
from run_job import run_job

SEEDS=[1495656323,1630784693]
HISTORY=ROOT.parent/'rl_b_autonomous_replication_v1'
FIRST='control_seed1495656323_first5__repair1'

def original(seed,ep=50):return str(HISTORY/f'seeds/{seed}/stage1/checkpoints/episode_{ep:03d}')
def config_job(job,**cfg):
    p=ROOT/'configs'/f'{job}.json';value=dict(job_id=job,**cfg)
    if p.exists():assert read(p)==value,'CONFIG_IDENTITY_CHANGED'
    else:atomic(p,value)
    return p
def execute(path):
    cfg=read(path);job=cfg['job_id']
    if (ROOT/'jobs'/job/'END.json').exists():end=read(ROOT/'jobs'/job/'END.json')
    else:end=run_job(path)
    if not end['success']:
        failure=read(RUNTIME/'jobs'/job/'FAILURE.json',end)
        decision('JOB_FAILED',failure,'Agent diagnosis or next independent safe branch',job=job)
        raise RuntimeError(f'JOB_FAILED:{job}')
    return read(RUNTIME/'jobs'/job/'RESULT.json')
def train(branch,seed,parent,start,count,lr,rollout='episode',reward='R0'):
    job=f'{branch}_seed{seed}_to{start+count:03d}'
    p=config_job(job,branch=branch,seed=seed,parent_checkpoint=parent,start_episode=start,
             episodes=count,mode='training',learning_rate=lr,rollout=rollout,reward=reward,target_kl=None)
    result=execute(p)
    return result['checkpoint']
def evaluate(branch,seed,checkpoint,episode,policy_mode='deterministic',rng=2026102101,label='dev1'):
    job=f'{branch}_seed{seed}_ep{episode:03d}_{policy_mode}_{label}'
    p=config_job(job,branch=branch,seed=seed,parent_checkpoint=checkpoint,start_episode=episode,
             episodes=1,mode='evaluation',policy_mode=policy_mode,evaluation_rng=rng,reward='R0',
             learning_rate=0.,rollout='episode',target_kl=None)
    return execute(p)['rows'][0]
def assess(rows):
    return dict(deterministic=[r['success'] for r in rows if r['policy_mode']=='deterministic'],
                stochastic=[r['success'] for r in rows if r['policy_mode']=='stochastic'])
def identity_control(seed,job):
    # Pure saved-state check, the same venv is used by a separate audit utility.
    import subprocess
    py=ROOT.parent/'rl_b_matched_recovery_stability_v1/cpu-env/bin/python'
    p=subprocess.run([str(py),str(ROOT/'scripts/control_identity.py'),str(seed),job],
                     capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=60)
    atomic(ROOT/'audit'/f'CONTROL_IDENTITY_PROCESS_{seed}.json',dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    return read(ROOT/'audit'/f'CONTROL_IDENTITY_{seed}.json',dict(pass_=False))

def main():
    atomic(ROOT/'CAMPAIGN_PROCESS.json',dict(identity=pid_identity(os.getpid()),time_utc=now(),finite_queue=True))
    branches={};evaluations={};stage='CONTROL';error=None
    try:
        # The initial supervised job was launched during tool preparation.
        while not (ROOT/'jobs'/FIRST/'END.json').exists():
            check_resources();time.sleep(2)
        end=read(ROOT/'jobs'/FIRST/'END.json')
        if not end['success']:raise RuntimeError('INITIAL_CONTROL_NEEDS_ENGINEERING_REPAIR')
        controls={SEEDS[0]:FIRST}
        seed=SEEDS[1]
        cp=train('CONTROL_IDENTITY',seed,original(seed),0,5,.0003)
        controls[seed]=f'CONTROL_IDENTITY_seed{seed}_to005'
        identities={seed:identity_control(seed,job) for seed,job in controls.items()}
        strict=all(x.get('pass_',False) for x in identities.values())
        atomic(ROOT/'audit/CONTROL_REUSE_DECISION.json',dict(strict_paired_reuse=strict,identities=identities,
            original_control_episodes='051–080',scope='Two selected successful checkpoint050 parents; not from-scratch multiseed replication'))
        decision('CONTROL_IDENTITY',dict(strict_paired_reuse=strict),
                 'Reuse original Control if exact; otherwise bounded full matched continuation',
                 hypothesis='Copied runtime and restored state reproduce original continuation')
        if not strict:
            for seed,job in controls.items():
                cp=read(RUNTIME/'jobs'/job/'RESULT.json')['checkpoint']
                cp=train('CONTROL_NEW',seed,cp,5,25,.0003)
        stage='H1';h1={seed:original(seed) for seed in SEEDS};h1eval=[]
        for target in [10,20,30]:
            for seed in SEEDS:
                h1[seed]=train('H1',seed,h1[seed],target-10,10,.0001)
                for mode in ['deterministic','stochastic']:
                    h1eval.append(evaluate('H1',seed,h1[seed],target,mode))
            atomic(ROOT/'H1_STABILITY_RESULTS.json',dict(status='DEVELOPMENT_IN_PROGRESS' if target<30 else 'COMPLETE_DEVELOPMENT',
                   target=target,checkpoints=h1,evaluations=h1eval,control_reused=strict))
            decision('H1_CHECKPOINT',assess(h1eval[-4:]),'Continue prespecified H1 to30 or proceed to H2',
                     target=target,remaining=read(ROOT/'LEDGER.json'))
        branches['H1']=dict(checkpoints=h1,lr=.0001,rollout='episode',reward='R0')
        evaluations['H1']=h1eval
        h1_final=[x for x in h1eval if x['index']==31]
        # index is continuation endpoint+1 for a single frozen attempt.
        h1_good=all(x['success'] for x in h1_final if x['policy_mode']=='deterministic') and len(h1_final)==4
        stage='H2';h2={};h2eval=[]
        # Even a positive H1 leaves the independently motivated update-noise question valuable.
        decision('H2_START',dict(h1_final=assess(h1_final),h1_consistent_nominal_retention=h1_good),
                 'Test complete-episode aggregation with original LR and R0, holding parent/action/model fixed',
                 hypothesis='Aggregation reduces singleton/short-episode advantage noise',budget_training=60,budget_evaluation=4)
        for seed in SEEDS:
            h2[seed]=train('H2_AGG64',seed,original(seed),0,30,.0003,'aggregate64')
            for mode in ['deterministic','stochastic']:h2eval.append(evaluate('H2_AGG64',seed,h2[seed],30,mode))
        branches['H2_AGG64']=dict(checkpoints=h2,lr=.0003,rollout='aggregate64',reward='R0')
        evaluations['H2_AGG64']=h2eval
        def rank(name):
            rows=[x for x in evaluations[name] if x['index']==31]
            return (sum(x['success'] for x in rows if x['policy_mode']=='deterministic'),
                    sum(x['success'] for x in rows if x['policy_mode']=='stochastic'))
        stability=max(branches,key=rank);base=branches[stability]
        atomic(ROOT/'STABILITY_SELECTION.json',dict(selected=stability,ranking={k:rank(k) for k in branches},
               limitation='Development nominal endpoint selection, no generalization or formal stability qualification'))
        decision('REWARD_BASE_SELECTION',dict(selected=stability,ranking={k:rank(k) for k in branches}),
                 'Compare pre-audited R1 and R2 on common original050 parents under the selected PPO configuration')
        stage='REWARD'
        for reward in ['R1','R2']:
            cps={};ev=[];branch='REWARD_'+reward
            for seed in SEEDS:
                cps[seed]=train(branch,seed,original(seed),0,10,base['lr'],base['rollout'],reward)
                for mode in ['deterministic','stochastic']:ev.append(evaluate(branch,seed,cps[seed],10,mode))
            # Clear rejection at both modes/seeds avoids spending 40 more episodes on no signal.
            extend=any(x['success'] for x in ev)
            decision('REWARD_REFLECTION',dict(version=reward,initial10=assess(ev),extend=extend),
                 'Extend both seeds to30' if extend else 'Reject this branch; preserve failures and proceed to next Reward',
                 reason='At least one frozen completion is necessary for extending this small development screen')
            if extend:
                for seed in SEEDS:
                    cps[seed]=train(branch,seed,cps[seed],10,20,base['lr'],base['rollout'],reward)
                    for mode in ['deterministic','stochastic']:ev.append(evaluate(branch,seed,cps[seed],30,mode))
            branches[branch]=dict(checkpoints=cps,lr=base['lr'],rollout=base['rollout'],reward=reward,
                                  endpoint=30 if extend else 10)
            evaluations[branch]=ev
            atomic(ROOT/'REWARD_SEARCH_RESULTS.json',dict(status='RUNNING',branches=branches,evaluations=evaluations))
        atomic(ROOT/'FINITE_QUEUE_COMPLETE.json',dict(time_utc=now(),branches=branches,evaluations=evaluations,
                  next='Agent reflection: optional third reward, retention extension, unseen action-stream verification, final scientific audit'))
        decision('FINITE_QUEUE_COMPLETE',dict(branches=list(branches),budget=read(ROOT/'LEDGER.json')),
                 'Agent reviews evidence and allocates remaining bounded research; never automatically launch final Campaign')
        atomic(ROOT/'RESEARCH_STATE.json',dict(**read(ROOT/'RESEARCH_STATE.json'),status='AWAITING_AGENT_RESEARCH_REVIEW',
              phase=stage,time_utc=now(),next='Read FINITE_QUEUE_COMPLETE.json and decide evidence-supported remaining work'))
    except BaseException as exc:
        error=dict(error=repr(exc),traceback=traceback.format_exc())
        atomic(ROOT/'QUEUE_FAILURE.json',dict(stage=stage,time_utc=now(),**error))
        decision('QUEUE_CHECKPOINT',dict(stage=stage,**error),'Agent repairs or switches safe branch; local failure is not global STOP')
        atomic(ROOT/'RESEARCH_STATE.json',dict(**read(ROOT/'RESEARCH_STATE.json'),status='NEEDS_AGENT_DIAGNOSIS',phase=stage,error=error,time_utc=now()))
    finally:atomic(ROOT/'CAMPAIGN_QUEUE_END.json',dict(time_utc=now(),phase=stage,error=error,formal_campaign_started=False))

if __name__=='__main__':main()
