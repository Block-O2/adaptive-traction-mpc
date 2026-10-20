"""Verify the stopped continuation's serialized state without loading SAC or physics."""
from pathlib import Path
import hashlib,json,zipfile,subprocess,shutil,time

R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
NAME='single_human_sac_seed1_continuation_v2_guardfix_attempt3'
D=S/'docs'/NAME;P=S/'scripts'/NAME
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_seed1_continuation')
L=W/'output_attempt3'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    state=read(D/'STATE.json');bundle=read(D/'SAVED_BUNDLE.json')
    assert state['status'] in ('SAC_SEED1_300K_COMPLETE','SAC_SEED1_SAVED_STOP'),state
    assert bundle['tag']=='final' and bundle['step']==state['step']
    for path,digest in bundle['files'].items():assert sha(Path(path))==digest,path
    checkpoint=next(Path(p) for p in bundle['files'] if p.endswith('.zip'))
    members=['policy.pth','actor.optimizer.pth','critic.optimizer.pth','ent_coef_optimizer.pth','pytorch_variables.pth']
    with zipfile.ZipFile(checkpoint) as z:
        assert z.testzip() is None
        assert all(k in z.namelist() for k in members)
        data=json.loads(z.read('data'))
        assert data['num_timesteps']==bundle['step'] and data['_n_updates']==bundle['updates']
        final_members={k:hashlib.sha256(z.read(k)).hexdigest() for k in members}
    original=read(W.parent/'single_human_sac_memory/output/SAVED_BUNDLE_VERIFICATION.json')
    for key,value in original['scientific_configuration_unchanged'].items():assert data[key]==value,key
    for name in ('SAC_CONTRACT_LOCK.json','SAC_EXPERT_V1_CONTRACT.json','SAC_OBSERVATION_NORMALIZATION.json','SAC_TRAINING_CONFIG.json'):
        expected=original['bundle_sha256'][name]
        assert sha(D/name)==expected and sha(checkpoint.parent/name)==expected,name
    pre=read(D/'PRESERVATION_BEFORE.json')
    changed=[p for p,h in pre['files'].items() if not (R/p).exists() or sha(R/p)!=h]
    assert not changed,changed
    assert subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)==pre['index']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pre['head']
    assert sha(P/'continue_seed1_v1.py')==sha(W/'continue_seed1_v3_guardfix.py')
    active=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        if cmd.startswith('/home/hank/envs/adaptive-online-rl-v1/bin/python') and 'continue_seed1_v3_guardfix.py' in cmd:active.append(dict(pid=int(proc.name),cmd=cmd))
    assert not active,active
    archives=[]
    roots=[S/'results/single_human_sac_seed1_continuation_v1_attempt2/saved_bundles',checkpoint.parent.parent/'saved_bundles']
    for path in sorted(p for root in roots for p in root.glob('*/VERIFIED_BUNDLE.json')):
        receipt=read(path)
        assert receipt['archive_verified']
        for p,h in receipt['archived_files'].items():assert sha(Path(p))==h,p
        archives.append(dict(path=str(path),sha256=sha(path)))
    proof=dict(status=state['status'],step=bundle['step'],updates=bundle['updates'],replay_size=bundle['replay_size'],bundle_sha256=bundle['files'],zip_crc_pass=True,serialized_optimizer_members_sha256=final_members,scientific_configuration_unchanged=original['scientific_configuration_unchanged'],preexisting_files_preserved=len(pre['files']),head_unchanged=True,index_unchanged=True,source_copy_unchanged=True,training_process_stopped=True,archived_milestone_receipts=archives,verified_unix=time.time())
    text=json.dumps(proof,indent=2,sort_keys=True)+'\n'
    for folder in (D,L):(folder/'FINAL_STATE_VERIFICATION.json').write_text(text)
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps(dict(status=state['status'],step=bundle['step'],zip_crc_pass=True,scientific_configuration_unchanged=True,preexisting_files_preserved=len(pre['files']),training_process_stopped=True)),flush=True)

if __name__=='__main__':run()
