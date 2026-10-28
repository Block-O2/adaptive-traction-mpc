from pathlib import Path
import subprocess,json,hashlib,datetime,time,shutil,re
R=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source');S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/single_human_sac_expert_v1';P=S/'scripts/single_human_sac_expert_v1_r2';O=S/'results/single_human_sac_expert_v1_r2'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2');W.mkdir(exist_ok=True)
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert git('branch','--show-current').strip()=='codex/single-human-sac-expert-v1'
assert json.loads((D/'STATE.json').read_text())['training_steps']==0
for p in (P,O):p.mkdir(exist_ok=False)
index=git('ls-files','--stage'); paths=[line.split('\t',1)[1] for line in index.splitlines()]
snap=dict(started_unix=time.time(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--short'),index_entries=index,worktree_hashes={p:sha(R/p) for p in paths if (R/p).is_file()},cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(R),'diff','--cached','--binary'])).hexdigest(),unstaged_diff=git('diff'),formal_steps=0)
(D/'GIT_PREFLIGHT_R2.json').write_text(json.dumps(snap,indent=2)+'\n')
shutil.copy2(W/'preflight_r2.py',P/'preflight_r2.py')
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/ac3ad582-c611-4d40-839d-06e041325665/已粘贴的文本.txt',D/'USER_REQUEST_R2.txt')
for name in ('SAC_EXPERT_V1_CONTRACT.json','COMPARATOR_old_nominal_MATCHED.json','SAC_COMPARATOR_TABLE.json','SAC_TRAINING_CONFIG.json','STATE.json'):
 shutil.copy2(D/name,W/name)
src=S/'src/traction_mpc_stage5'
pieces=[]
for p in src.rglob('*.py'):
 text=p.read_text()
 if 'def reference_safe_task_transition(' in text or p.name=='task.py':
  shutil.copy2(p,W/p.name);pieces.append(str(p.relative_to(R)))
(W/'stage5_goal_task_120_v1.json').write_bytes((S/'configs/high_rom_v1/stage5_goal_task_120_v1.json').read_bytes())
trace=R/json.loads((D/'COMPARATOR_old_nominal_MATCHED.json').read_text())['trace'];shutil.copy2(trace,W/'old_matched_trace.npz')
resources=dict(unix=time.time(),memory=Path('/proc/meminfo').read_text(),load=Path('/proc/loadavg').read_text(),processes=subprocess.check_output(['ps','-eo','pid,etimes,pcpu,pmem,rss,args','--sort=-pcpu'],text=True),vmstat=subprocess.check_output(['vmstat','1','3'],text=True),gpu=subprocess.check_output(['nvidia-smi'],text=True))
(D/'RESOURCE_PREFLIGHT_R2.json').write_text(json.dumps(resources,indent=2)+'\n')
print(json.dumps(dict(staged_entries=len(paths),unstaged_lines=len(snap['unstaged_diff'].splitlines()),source_files=pieces,WSL_MemAvailable=next(x for x in resources['memory'].splitlines() if x.startswith('MemAvailable')),vmstat=resources['vmstat'],processes=resources['processes'][:4500])))
