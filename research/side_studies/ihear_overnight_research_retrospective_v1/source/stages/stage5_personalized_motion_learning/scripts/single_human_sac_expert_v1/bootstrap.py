"""Inspect and freeze campaign provenance; preserve every pre-existing file/index entry."""
from pathlib import Path
import json, hashlib, subprocess, shutil, platform, datetime, time
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work')
D=S/'docs/single_human_sac_expert_v1'; P=S/'scripts/single_human_sac_expert_v1'; O=S/'results/single_human_sac_expert_v1'
def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
assert git('rev-parse','--show-toplevel')==str(R)
assert git('branch','--show-current')=='codex/adaptive-human-online-interface-v1'
assert not git('branch','--list','codex/single-human-sac-expert-v1')
pre=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),status=git('status','--short'),index=git('diff','--cached','--name-status'),remote=git('remote','-v'))
for d in (D,P,O):d.mkdir(parents=True,exist_ok=False)
pre['fingerprints']={str(p.relative_to(R)):sha(p) for p in S.rglob('*') if p.is_file() and ((p.suffix=='.py' and '/src/' in str(p)) or ('/configs/' in str(p) and p.suffix=='.json'))}
pre['historical_docs']={str(p.relative_to(R)):sha(p) for group in ('adaptive_human_online_interface_v1','direct_rl_expert_v1','best_known_coordination_search_v2') for p in (S/'docs'/group).rglob('*') if p.is_file()}
pre['preexisting_dirty_fingerprints']={line[3:]:sha(R/line[3:]) for line in pre['status'].splitlines() if (R/line[3:]).is_file()}
save(D/'GIT_PREFLIGHT.json',pre)
subprocess.run(['git','-C',str(R),'switch','-c','codex/single-human-sac-expert-v1'],check=True)
assert git('diff','--cached','--name-status')==pre['index']
save(D/'SOURCE_FINGERPRINTS.json',dict(source_commit=pre['head'],protected_files=pre['fingerprints'],historical_docs=pre['historical_docs'],dirty_source=pre['preexisting_dirty_fingerprints']))
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/69f86a34-ee3d-4f14-be99-a1bc122f5f85/已粘贴的文本.txt',D/'USER_REQUEST.txt')
shutil.copy2(W/'bootstrap.py',P/'bootstrap.py')
for name in ('runtime_online_v1.py','online_reference.py','online_gym.py'):
    shutil.copy2(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1'/name,W/name)
save(D/'STATE.json',dict(status='QUALIFICATION_IN_PROGRESS',phase='CONTRACT_DEVELOPMENT',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),started_unix=time.time(),branch=git('branch','--show-current'),head=pre['head'],formal_training_started=False,training_steps=0,hard_wall_hours=12,next_action='Freeze versioned adapter and prospectively specified qualification protocol.',committed=False,pushed=False))
save(D/'RESOURCE_PREFLIGHT.json',dict(host=platform.node(),os=Path('/etc/os-release').read_text(),memory=Path('/proc/meminfo').read_text(),disk=subprocess.check_output(['df','-B1','/','/mnt/c'],text=True),gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free,utilization.gpu','--format=csv'],text=True),max_envs=1))
print(json.dumps(dict(branch=git('branch','--show-current'),head=pre['head'],preexisting_staged_files=len(pre['index'].splitlines()),protected_files=len(pre['fingerprints']),docs=str(D))))
