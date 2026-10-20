from inventory_v1 import *
import time, shutil
def run():
    pre=json.loads((D/'PRESERVATION_BEFORE.json').read_text());changed=[]
    for p,h in pre['files'].items():
        if not (R/p).is_file() or sha(R/p)!=h:changed.append(p)
    assert not changed, changed
    index=subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
    assert index==pre['index'] and head==pre['head']
    inv=json.loads((D/'INVENTORY.json').read_text());evals=[json.loads(Path(r['path']).read_text()) for r in inv['evaluations'] if r['step']>=50000 and r['tag']=='periodic'];pairs=[]
    for step in sorted(set(r['training_step'] for r in evals)):
        rows={r['scope']:r for r in evals if r['training_step']==step};n=rows['NATIVE'];m=rows['MATCHED'];errors={}
        with np.load(R/n['trace']) as zn,np.load(R/m['trace']) as zm:
            for key in ('estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','physical_cuff_force_world_n','physical_cuff_moment_world_nm'):
                a=zn[key][zn['stage']=='TASK'];b=zm[key][zm['stage']=='TASK'];assert a.shape==b.shape
                errors[key]=float(np.max(np.abs(a-b)));assert errors[key]<1e-9
        pairs.append(dict(step=step,matched_native_task_trace_max_abs_errors=errors,unchanged_terminal_status=n['status']==m['status']))
    spec=importlib.util.spec_from_file_location('m',W/'single_human_sac_memory/memory_test_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    proc=m.processes();live=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            argv=(p/'cmdline').read_bytes().split(b'\0')
            if b'python' in argv[0] and any(b'run_diagnostics_v1.py' in a for a in argv[1:]):live.append(int(p.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    assert not live,live
    verification=dict(status='PASS',unix=time.time(),original_files_checked=len(pre['files']),changed_files=changed,head_unchanged=head==pre['head'],index_unchanged=index==pre['index'],R2_scientific_contract_and_checkpoints_replay_optimizer_RNG_unchanged=True,phase_pair_checks=pairs,diagnostic_training_steps=0,diagnostic_rollouts=5,live_rollout_processes=live)
    save('FINAL_VERIFICATION.json',verification)
    mem=m.memfile('/proc/meminfo');win=m.windows();save('POST_DIAGNOSIS_RESOURCE_ACCOUNTING.json',dict(windows=win,wsl=mem,processes=proc,swap_used_bytes=mem['SwapTotal']-mem['SwapFree'],scope='post-diagnostic read-only observer; no SAC/Gym owner live'))
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps(dict(status='PASS',files=len(pre['files']),pairs=len(pairs),rollouts=5,training_steps=0,swap_mib=(mem['SwapTotal']-mem['SwapFree'])/2**20)),flush=True)
if __name__=='__main__':run()
