from pathlib import Path
import sys, json, subprocess, hashlib, importlib.util
import numpy as np
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source');S=R/'stages/stage5_personalized_motion_learning'
NAME='single_human_sac_seed1_300k_failure_diagnosis_v1'
D=S/'docs'/NAME;O=S/'results'/NAME;P=S/'scripts'/NAME;L=W/'single_human_sac_failure_diagnosis/output'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(name,row):
    def clean(v):
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
        if isinstance(v,list):return [clean(x) for x in v]
        if isinstance(v,float) and not np.isfinite(v):return None
        return v
    for p in (D,L):(p/name).write_text(json.dumps(clean(row),indent=2,sort_keys=True,allow_nan=False)+'\n')
def run():
    for p in (D,O,P,L):p.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('m',W/'single_human_sac_memory/memory_test_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    if not (D/'PRESERVATION_BEFORE.json').exists():
        pre=m.snapshot()
        latest=S/'docs/single_human_sac_seed1_continuation_v2_guardfix_attempt3/SAVED_BUNDLE.json'
        for p in json.loads(latest.read_text())['files']:pre['files'][str(Path(p).relative_to(R))]=sha(Path(p))
        save('PRESERVATION_BEFORE.json',pre)
    save('DIAGNOSTIC_PLAN.json',dict(question='Seed1/300k full-task acquisition and failure diagnosis',training_steps_authorized_and_run=0,max_new_rollouts=6,planned_rollouts=['fixed_hip_lead NATIVE same wrapper','fixed_hip_lead MATCHED same wrapper','300k deterministic NATIVE with reward/observation logging','early_failure NATIVE','no_motion NATIVE'],scientific_changes=[],replay_coverage='offline sample of saved final replay only',optimization='read-only checkpoint metrics; no optimizer step',ranking='complete independently physical VALID trajectories only; INVALID J_F never ranked',truth='evaluation-only post-run diagnosis; policy remains causal',resource_guard='WSL available>=1.5GiB, Windows commit headroom>=2GiB, no sustained/new swap, no other heavy experiment',seeds=[20261003]))
    folders=[S/'docs/single_human_sac_seed1_continuation_v1_attempt2',S/'docs/single_human_sac_seed1_continuation_v2_guardfix_attempt3',S/'docs/single_human_sac_expert_v1/r2',S/'docs/single_human_sac_memory_v1/attempt5']
    rows=[]
    for folder in folders:
        for path in sorted(folder.glob('EVALUATION_*.json')):
            row=json.loads(path.read_text())
            if not isinstance(row,dict) or 'training_step' not in row:continue
            rows.append(dict(path=str(path),step=row['training_step'],scope=row['scope'],tag=row['tag'],trace=row['trace'],trace_sha256=row['trace_sha256']))
    main=[r for r in rows if r['step']>=50000 and r['tag']=='periodic'];assert len(main)==22
    sample=json.loads(Path(main[-1]['path']).read_text());trace=R/sample['trace'];ep=trace.parent
    info=dict(evaluation_keys=list(sample),episode_files=[p.name for p in ep.iterdir()],summary=json.loads((ep/'summary.json').read_text()))
    with np.load(trace) as z:info['trace']={k:dict(shape=list(z[k].shape),dtype=str(z[k].dtype),first=z[k][0].tolist() if z[k].ndim and len(z[k]) else None) for k in z.files}
    with np.load(ep/'SAC_ACTOR_ACTIONS.npz') as z:info['actions']={k:dict(shape=list(z[k].shape),dtype=str(z[k].dtype),first=z[k][0].tolist() if len(z[k]) else None) for k in z.files}
    save('INVENTORY.json',dict(evaluations=rows,sample=info))
    resources=dict(windows=m.windows(),wsl=m.memfile('/proc/meminfo'),processes=m.processes(),gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip())
    save('RESOURCE_PREFLIGHT.json',resources)
    import shutil;shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps(dict(evaluations=len(rows),primary22=len(main),trace_keys=list(info['trace']),summary_keys=list(info['summary']),windows_available_gib=resources['windows']['AvailableBytes']/2**30,wsl_available_gib=resources['wsl']['MemAvailable']/2**30,other_heavy=resources['processes']['other_heavy_python'])),flush=True)
if __name__=='__main__':run()
