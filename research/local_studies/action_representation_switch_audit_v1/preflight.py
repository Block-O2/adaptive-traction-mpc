from common import *
def run():
    assert not O.exists(),'REFUSE_OVERWRITE';O.mkdir()
    def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
    files=set(git('ls-files','-z').split('\0')+git('ls-files','--others','--exclude-standard','-z').split('\0'))
    protected={p:sha(R/p) for p in files if p and (R/p).is_file()}
    for root in (BC,S/'docs/demo_assisted_sac_task_acquisition_v1',S/'docs/single_human_sac_expert_v1',S/'results/bc_reproduction_gate_v1',DEMO.parent):
        for p in root.rglob('*'):
            if p.is_file():protected[str(p.relative_to(R))]=sha(p)
    local={str(p.relative_to(W)):sha(p) for root in (W/'bc_reproduction_gate_v1',W/'demo_assisted_sac_task_acquisition_v1',W/'single_human_sac_r2') for p in root.rglob('*') if p.is_file()}
    before=dict(branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),index=git('ls-files','--stage'),status=git('status','--short'),files=protected,windows_files=local)
    save('PRESERVATION_BEFORE.json',before)
    branch='codex/action-representation-switch-audit-v1'
    subprocess.run(['git','switch','-c',branch],cwd=R,check=True)
    assert git('ls-files','--stage')==before['index']
    old=json.loads((BC/'SCIENTIFIC_LOCK.json').read_text());save('SOURCE_LOCK.json',old['files'])
    lock();spec=json.loads((BC/'PREREGISTRATION.json').read_text())
    save('PLAN_FROZEN.json',dict(status='DIAGNOSTIC_DEVELOPMENT_ONLY',branch=branch,source_head=before['head'],seeds=spec['seeds'],initial_condition_seed=spec['initial_condition_seed'],scope='NATIVE',policy_period_s=.02,max_rollouts=3,SAC_steps=0,teacher_override=False,old_gate_unchanged=True,offline_split=spec['split'],fit_optimizer=spec['optimizer'],fit_sampling=spec['sampling'],fit_budget=spec['budget'],fit_selection=spec['selection'],first_divergence='first five consecutive normalized observation L2 > .25, aligned to nearest teacher time; also physical q error >5deg for five consecutive policy observations',R2='delta_previous_raw: d=(a-a_previous)/2; a=clip(a_previous+2*d,-1,1); previous raw action features49:51; same certified target layer',R3='bounded legal owned-continuation velocity at next policy boundary; investigate deployability and equivalence before any fit; skip if equivalent safe adapter is unsupported',promotion='No control-performance claim from alternative offline fits; no alteration of prior gates',truth='physical truth post-run evaluation only; actors see unchanged55D',prohibited=['SAC','hyperparameter_search','DAgger','curriculum','PPO','TQC','reward_change','safety_change','hardware']))
    save('ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,torch=torch.__version__,cuda=torch.cuda.is_available(),command='wsl -d Ubuntu -- bash /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/action_representation_switch_audit_v1/launch.sh'))
    save('STATE.json',dict(status='PREREGISTERED',next='offline audit then three diagnostic replays then eligible representation fits'))
    resources('PREFLIGHT');print('PREFLIGHT PASS',len(protected),flush=True)
if __name__=='__main__':run()
