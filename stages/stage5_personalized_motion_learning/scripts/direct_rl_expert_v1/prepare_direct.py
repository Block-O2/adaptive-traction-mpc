"""Freeze new campaign evidence; never alter production or historical files."""
from pathlib import Path
import hashlib, json, subprocess, shutil, sys, os, platform
from datetime import datetime, timezone

R = Path('/home/hank/coding/adaptive-traction-mpc-learning')
S = R / 'stages/stage5_personalized_motion_learning'
P = S / 'scripts/direct_rl_expert_v1'
D = S / 'docs/direct_rl_expert_v1'
RAW = S / 'results/direct_rl_expert_v1'
W = Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/direct_rl_expert_work')

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def save(p, x): p.write_text(json.dumps(x, indent=2, sort_keys=True, allow_nan=False)+'\n')
def git(*args): return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()

assert git('branch','--show-current') == 'codex/direct-rl-expert-v1'
assert git('status','--short') == ''
for p in (P,D,RAW): p.mkdir(parents=True,exist_ok=False)
for name in ('prepare_direct.py','safety_probe.py'):
    shutil.copy2(W/name,P/name)
request = Path('/mnt/c/Users/HankL/.codex/attachments/eaf61249-aa7a-4a6a-a4c8-aa5841b311b5/已粘贴的文本.txt')
shutil.copy2(request,D/'USER_REQUEST.txt')
source = git('rev-parse','HEAD')
protected = {}
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    for p in (R/'stages'/stage/'src').rglob('*.py'): protected[str(p.relative_to(R))] = sha(p)
for p in (S/'configs').rglob('*.json'): protected[str(p.relative_to(R))]=sha(p)
evidence = {}
for group in ('zero_value_30rep_baseline_v3','coordination_pacing_exploration_v1','value_learning_research_v1','best_known_coordination_search_v2'):
    evidence[group] = {str(p.relative_to(R)):sha(p) for p in (S/'docs'/group).iterdir() if p.is_file() and p.suffix in ('.json','.md','.csv')}
for name in ('RESOURCE_AUDIT_V1_REPORT.md','GIT_WORKTREE_AUDIT.json','RESEARCH_MEMORY_ARCHITECTURE_AUDIT.json'):
    p=W.parent/'resource_audit_v1'/name
    evidence.setdefault('resource_audit_v1',{})[str(p)]=sha(p)
for name in ('CONTROLLED_CLEANUP_V1_REPORT.md','CLEANUP_STATE.json'):
    p=W.parent/'cleanup_archive_v1'/name
    evidence.setdefault('cleanup_archive_v1',{})[str(p)]=sha(p)
save(D/'SOURCE_FINGERPRINTS.json',{'source_commit':source,'protected_files':protected,'evidence_files':evidence,'user_request_sha256':sha(D/'USER_REQUEST.txt')})
refs=['codex/zero-value-30rep-baseline-v3','codex/coordination-pacing-exploration-v1','codex/value-learning-research-v1','codex/best-known-coordination-search-v2']
remote=subprocess.run(['git','-C',str(R),'ls-remote','--heads','origin',*refs],text=True,capture_output=True,timeout=60)
reachable={line.split()[1].removeprefix('refs/heads/'):line.split()[0] for line in remote.stdout.splitlines()}
save(D/'GIT_PREFLIGHT.json',{'initial_branch':'codex/best-known-coordination-search-v2','initial_head':source,'initial_status_short':'','branch':git('branch','--show-current'),'remote_query_returncode':remote.returncode,'local_heads':{x:git('rev-parse',x) for x in refs},'remote_heads':reachable,'latest_best_known_v2_pushed':reachable.get(refs[-1])==source,'push_authorized_in_this_chat':False,'merged':False})
gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu','--format=csv'],text=True)
save(D/'RESOURCE_PREFLIGHT.json',{'utc':datetime.now(timezone.utc).isoformat(),'host':platform.node(),'os':Path('/etc/os-release').read_text(),'python':sys.version,'meminfo':Path('/proc/meminfo').read_text(),'swaps':Path('/proc/swaps').read_text(),'cpu':subprocess.check_output(['lscpu'],text=True),'disk':subprocess.check_output(['df','-B1','/','/mnt/c'],text=True),'process_count':len([x for x in Path('/proc').iterdir() if x.name.isdigit()]),'gpu_query':gpu,'max_environments':1,'physical_host_ram_bytes':16890322944,'scientific_env_torch':'not installed','existing_capstone_env_torch':'2.14.0+cpu','existing_capstone_env_torch_cuda':None,'existing_capstone_env_cuda_available':False,'training_device':None,'main_cpu_training_forbidden':True})
contract={'schema':'direct_rl_v1_contract','frozen_utc':datetime.now(timezone.utc).isoformat(),'source_commit':source,'branch':git('branch','--show-current'),'primary_score':'J_F_task = integral ||F_cuff_measured|| dt over COMPLETE OUTBOUND -> HOLD -> RETURN','quadrature':'existing 5ms left quadrature; preserve original terminal boundary accounting','acceptance':'unchanged independent physical/task/safety/scientific evaluator; early failure gets no ranked score','secondary':['mean/RMS/peak force','moment integral/peak','duration','minimum clearance','smoothness','success','safety intervention count'],'no_composite_paper_score':True,'conditions':['sync_120','low_ordinary_early'],'low_rom_context':'same source checkpoint repetition 1, adaptation state of existing ordinary session; not independent patient','development_split':'Both previously studied conditions; no held-out/generalization claim','action':'continuous Box[-1,1]^2, hip/knee bounded target changes; no old lattice projection','period_candidates_s':[0.02,0.05],'chosen_period_s':None,'physics':'same validated CPU MuJoCo, CR12-cuff physical path; no Human-state or torque actuation','actor_firewall':'estimated causal state/belief and measured wrench only; no truth, future, oracle geometry, CEM identity','rate_diagnostic_gate':'existing action/safety interface must support each period with reference continuity and complete task','gates':['source freeze','resource/CUDA','safety expanded-action compatibility','environment A-I validation','reward hacking audit','policy-period study','throughput','SAC pilot','independent evaluation','closeout'],'stop_conditions':['existing authoritative safety tied to old representation cannot screen expanded action','baseline mismatch requiring physical changes','hidden truth needed for actor','wall budget exhausted'],'wall_target_hours':[5,8],'hard_max_hours':10,'workers':1,'allow_two_workers':'only after RSS evidence; max2; never3+','training_budget':{'minimum_full_seed_steps':100000,'preferred_steps':[200000,300000],'second_seed':'full if time permits else shorter independent seed'},'reward':'negative measured force interval integral + task potential + optional valid completion bonus - explicit failure penalty; no action/coordination imitation reward; final reward not yet selected','curriculum':'only initialization difficulty/shaping strength; same physics/endpoints/evaluator','git':'stage individually; no merge; no force push; no push without existing/explicit authorization','retention':'compact training summaries/checkpoints; full traces only validation/evaluation/forensic; no bulk cleanup','terminal_states':['DIRECT_RL_SAC_V1_COMPLETE','DIRECT_RL_SAC_V1_PARTIAL','DIRECT_RL_SAC_V1_BLOCKED']}
save(D/'DIRECT_RL_V1_CONTRACT.json',contract)
(D/'DIRECT_RL_V1_CONTRACT.md').write_text('# Direct RL Expert Search v1 contract\n\nFrozen before compatibility probes or training. USER_REQUEST.txt contains the complete authoritative request. DIRECT_RL_V1_CONTRACT.json records gates and SOURCE_FINGERPRINTS.json pins physics, controller, safety, configuration and historical evidence.\n\nPrimary score is the existing measured cuff-force integral over a real COMPLETE OUTBOUND/HOLD/RETURN task. Task and safety validity are hard gates. Moment, intensity, duration, clearance and smoothness stay separate. Both conditions are previously studied development cases. CPU MuJoCo and CR12 physical execution remain unchanged.\n\nA continuous 2-D target-change interface must preserve authoritative safety. A failure of expanded-action screening stops main training, as explicitly required by user section 18. Policy rate and reward are not selected before their validation. CUDA is required for main SAC; no CPU fallback. One environment initially.\n')
save(D/'STATE.json',{'status':'PREFLIGHT_AND_COMPATIBILITY','phase':'SAFETY_INTERFACE_PROBE','training_steps':0,'main_training_started':False,'next_action':'python safety_probe.py','source_commit':source,'branch':git('branch','--show-current')})
print(json.dumps({'status':'CONTRACT_FROZEN','source':source,'protected_files':len(protected),'evidence_files':sum(map(len,evidence.values())),'remote_heads':reachable,'docs':str(D)}))
