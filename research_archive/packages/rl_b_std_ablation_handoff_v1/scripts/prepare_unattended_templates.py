from pathlib import Path
import json,shutil,hashlib
R=Path(__file__).resolve().parents[1];H=R.parent/'rl_b_autonomous_stability_reward_v1';T=R/'unattended/template'
if (T/'scripts/worker.py').exists():raise SystemExit('REVIEWED_TEMPLATES_EXIST: do not overwrite; use the final source manifest and next_launch.py')
(T/'scripts').mkdir(parents=True,exist_ok=True)
for name in ['worker.py','rewards.py','research_common.py','run_job.py','motion_metrics.py','watchdog.py']:
 shutil.copyfile(H/'scripts'/name,T/'scripts'/name)
p=T/'scripts/research_common.py';s=p.read_text().replace('RESERVATION = 165000',"RESERVATION = 165000\nLIMITS=STATE['limits']\nNATIVE_CAP=LIMITS['native_steps']")
s=s.replace("cap=450 if kind=='training' else 60","cap=LIMITS[kind+'_attempts']").replace('> 50000000','> NATIVE_CAP')
s=s.replace('HARD_STOP-300','HARD_STOP-900')
p.write_text(s)
p=T/'scripts/worker.py';s=p.read_text().replace('read, sha, reserve, settle, check_resources, now)','read, sha, reserve, settle, check_resources, now, NATIVE_CAP)')
s=s.replace('min(50000000,native_before+165000)','min(NATIVE_CAP,native_before+165000)').replace('HARD_STOP-300','HARD_STOP-900')
anchor="        # Loading verifies the full parent state before the sole intended config edit."
addition="""        # Next-stage only, never executed by the attended frozen study.
        # Start a new distribution identity with no old-distribution pending samples.
        if cfg.get('std_initialization') is not None:
            assert cfg['mode']=='training' and cfg.get('start_episode',0)==0
            assert not record.get('pending_complete_transitions',0), 'DISTRIBUTION_CHANGE_WITH_PENDING'
            assert cfg['std_initialization']==.2, 'ONLY_PREREGISTERED_STD_SCALE'
            preserved_optimizer=state_hash(model.policy.optimizer.state_dict())
            with torch.no_grad(): model.policy.log_std.fill_(math.log(.2))
            assert state_hash(model.policy.optimizer.state_dict())==preserved_optimizer
            write(out/'DISTRIBUTION_INITIALIZATION.json',dict(original=restored,
                after=snapshot(model),std=model.policy.log_std.detach().exp().tolist(),
                optimizer_inherited=True,learnable_log_std=True,pending_transitions=0,
                old_log_prob_reused=False,new_checkpoint_identity_required=True))
"""
assert anchor in s;s=s.replace(anchor,addition+anchor)
anchor='    singleton=0\n    if mode=='
addition="""    # Old densities must belong to exactly the current sampling distribution.
    with torch.no_grad():
        ot=torch.as_tensor(buf.observations.reshape(n,-1));at=torch.as_tensor(buf.actions.reshape(n,-1))
        _, lp_check, _=model.policy.evaluate_actions(ot,at)
        old_lp=np.asarray([s['logp'] for s in samples],dtype=np.float32)
        error=float(np.max(np.abs(lp_check.numpy()-old_lp)))
    write(out/'SAMPLING_DENSITY_OWNERSHIP.json',dict(max_abs_old_logp_error=error,
        raw_unclipped_actions=True,transitions=n,initial_ratio_should_be_one=True,
        policy_sha256=policy_hash(model),std=model.policy.log_std.detach().exp().tolist()))
    assert error<2e-5,'SAMPLING_DENSITY_OWNERSHIP_MISMATCH'
    singleton=0
    if mode=="""
assert anchor in s;s=s.replace(anchor,addition)
# Durable generation payloads + metadata commit marker, without editing frozen checkpoints.py.
anchor='def clean(obj): return common.clean(obj)'
addition="""_original_save=save
def save(model,base,metadata):
    result=_original_save(model,base,metadata)
    for suffix in ['.zip','.rng.pt','.json']:
        with Path(base).with_suffix(suffix).open('rb') as handle: os.fsync(handle.fileno())
    descriptor=os.open(str(Path(base).parent),os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    return result

"""
s=s.replace(anchor,addition+anchor)
p.write_text(s)
p=T/'scripts/rewards.py';s=p.read_text()+"\nVERSIONS['R4']={**VERSIONS['R1'],'version':'R4_R1_moment_price_0p020','moment_per_Nms':.020,'rationale':'Single preregistered moment-price hypothesis; all costs/floor independently recomputed.'}\n";p.write_text(s)
# Remove misleading legacy budget telemetry, use actual activated limits in records.
p=T/'scripts/research_common.py';s=p.read_text().replace('training_hard_cap=450,evaluation_hard_cap=60,native_hard_cap=50000000',"training_hard_cap=LIMITS['training_attempts'],evaluation_hard_cap=LIMITS['evaluation_attempts'],native_hard_cap=NATIVE_CAP")
s=s.replace("'10-hour hard deadline','450 training/60 evaluation/50M native caps'","'Activated 8-hour hard deadline','160 training/36 evaluation/33M native caps'")
p.write_text(s)
identity={str(p.relative_to(T)):hashlib.sha256(p.read_bytes()).hexdigest() for p in T.rglob('*') if p.is_file()}
(R/'unattended/TEMPLATE_IDENTITY.json').write_text(json.dumps(dict(files=identity,status='PREPARED_NOT_STARTED',training_this_stage=0),indent=2)+'\n')
print('prepared future-only worker, density guard, R4, dynamic budgets; no execution')
