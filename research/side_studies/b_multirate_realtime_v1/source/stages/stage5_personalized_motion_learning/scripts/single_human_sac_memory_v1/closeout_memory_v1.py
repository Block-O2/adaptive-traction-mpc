"""Verify saved bundle/config/index, preserve new memory evidence; no training."""
from pathlib import Path
import json,hashlib,shutil,subprocess,zipfile,time
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_multirate_realtime_v1/source');S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/single_human_sac_memory_v1';P=S/'scripts/single_human_sac_memory_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_memory');A=D/'attempt5'
OLD=S/'docs/single_human_sac_expert_v1/r2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def run():
    result=json.loads((W/'output/SAC_MEMORY_RESULT.json').read_text());final=result['final'];cp=Path(final['checkpoint']);folder=cp.parent
    with zipfile.ZipFile(cp) as z:
        assert z.testzip() is None;files=z.namelist();data=json.loads(z.read('data'))
    with zipfile.ZipFile(S/'results/single_human_sac_expert_v1_r2/seed_20261003/step_0012194.zip') as z:original=json.loads(z.read('data'))
    keys=('learning_rate','buffer_size','learning_starts','batch_size','tau','gamma','gradient_steps','ent_coef','target_entropy','train_freq','policy_kwargs','replay_buffer_kwargs')
    assert all(data[k]==original[k] for k in keys)
    assert data['num_timesteps']==30000 and data['_n_updates']==24997
    required=['policy.pth','actor.optimizer.pth','critic.optimizer.pth','ent_coef_optimizer.pth','pytorch_variables.pth']
    assert all(k in files for k in required),files
    for name in ('SAC_OBSERVATION_NORMALIZATION.json','SAC_CONTRACT_LOCK.json','SAC_TRAINING_CONFIG.json','SAC_EXPERT_V1_CONTRACT.json'):
        dest=folder/name;shutil.copy2(OLD/name,dest);assert sha(dest)==sha(OLD/name)
    for name in ('memory_test_v1.py','evaluation_peak_monitor_v1.py','analyze_memory_v1.py','plot_memory_v1.py','closeout_memory_v1.py'):
        shutil.copy2(W/name,P/name)
    for name in ('SAC_MEMORY_RESULT.json','SAC_MEMORY_REPORT_V1.md','SAC_MEMORY_FIGURE_V1.png','WSL_CONFIGURATION.txt','WINDOWS_EXTERNAL_WORKLOAD.json'):
        shutil.copy2(W/'output'/name,D/name)
    # Verify the true user-task startup, not an intermediate attempt snapshot
    # that also contains this task's intentionally mutable global STATE.json.
    pre=json.loads((D/'PRESERVATION_BEFORE.json').read_text())
    bounded_pre=json.loads((A/'PRESERVATION_BEFORE.json').read_text())
    failed=[path for path,h in pre['files'].items() if not (R/path).exists() or sha(R/path)!=h]
    assert not failed,failed
    assert subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)==pre['index']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pre['head']
    live=subprocess.check_output(['ps','-eo','pid,ppid,rss,args'],text=True)
    assert not any('memory_test_v1.py' in row and ' -c ' not in row and 'closeout_memory_v1' not in row for row in live.splitlines())
    mutable=str((D/'STATE.json').relative_to(R))
    bounded_failed=[path for path,h in bounded_pre['files'].items() if path!=mutable and (not (R/path).exists() or sha(R/path)!=h)]
    assert not bounded_failed,bounded_failed
    manifest=dict(status='SAC_MEMORY_QUALIFIED',step=30000,updates=24997,checkpoint=str(cp),scientific_configuration_unchanged={k:data[k] for k in keys},zip_crc_pass=True,optimizer_archive_members=required,bundle_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()},source_sha256={p.name:sha(p) for p in P.iterdir() if p.is_file()},preexisting_files_preserved=len(pre['files']),bounded_snapshot_files_preserved_except_own_global_state=len(bounded_pre['files'])-1,own_memory_global_state_finalized=mutable,own_state_was_not_present_at_user_task_start=mutable not in pre['files'],index_unchanged=True,head=pre['head'],branch=pre['branch'],training_stopped=True,no300k_run=True,resource_policy='SAC_MEMORY_POLICY_V2',elapsed_unix=time.time())
    write(D/'SAVED_BUNDLE_VERIFICATION.json',manifest);write(W/'output/SAVED_BUNDLE_VERIFICATION.json',manifest)
    state=dict(status='SAC_MEMORY_QUALIFIED',phase='SAVED_STOP',training_steps=30000,checkpoint=str(cp),replay=final['replay'],scientific_r2_unchanged=True,next_action='STOP. On a separately requested continuation, resume30k with resource policyV2 and retained accounting/evaluation peak monitoring; no capacity/RAM/swap change.')
    write(D/'STATE.json',state);write(W/'output/STATE.json',state)
    print(json.dumps(dict(status=state['status'],step=30000,updates=24997,preexisting_preserved=len(pre['files']),checkpoint=cp.name,configuration_keys_pass=len(keys),bundle=list(manifest['bundle_sha256'])),indent=2))
if __name__=='__main__':run()
