from pathlib import Path
import sys, json, hashlib, subprocess, shutil, ast
from datetime import datetime, timezone
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/adaptive_human_online_interface_v1'
W=S/'scripts/adaptive_human_online_interface_v1'
D.mkdir(exist_ok=False); W.mkdir(exist_ok=False)
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x): (D/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
assert git('branch','--show-current')=='codex/adaptive-human-online-interface-v1'
assert git('status','--porcelain')==''
source=git('rev-parse','HEAD')
save('GIT_PREFLIGHT.json',dict(source_commit=source,source_branch='codex/direct-rl-expert-v1',initial_status='',branch=git('branch','--show-current'),source_remote_verified='41cdddef117caa4b191a52129c4ff83e481fd5a8',remote_heads=git('ls-remote','--heads','origin'),commit_authorized=False,push_authorized=False,merge_authorized=False))
files=[p for p in S.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.xml','.toml') and not any(x in p.parts for x in ('results','__pycache__','vendor'))]
save('SOURCE_FINGERPRINTS.json',{str(p.relative_to(R)):sha(p) for p in files})
case_names=['high_rom_nominal_sync_120_v1','high_rom_matrix_light_soft_sync_v1','high_rom_matrix_heavy_stiff_sync_v1','high_rom_matrix_short_segments_sync_v1']
cases=[dict(id=n,path=str((S/'configs/high_rom_v1'/f'{n}.json').relative_to(R)),sha256=sha(S/'configs/high_rom_v1'/f'{n}.json'),case=json.loads((S/'configs/high_rom_v1'/f'{n}.json').read_text())) for n in case_names]
opt=S/'configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json'
save('EXPERIMENT_CONTRACT.json',dict(frozen_utc=datetime.now(timezone.utc).isoformat(),source_commit=source,questions={'A':'Current effective Human updates are consumed in full CR12 execution and differ across a bounded inherited Human domain.','B':'Acceleration-aware short commitment permits immediate future reference changes with existing physics/safety.'},cases=cases,arms=['fixed_population','commissioning_only','continual_adaptive'],options_path=str(opt.relative_to(R)),options_sha256=sha(opt),fallback_scope='If 120-degree truth fails, preserve failure; any lower-ROM alternative must be a separately recorded existing task, never threshold relaxation.',evidence_category='current_version_development_qualification_not_held_out',seed='existing runtime measurement seed unchanged',truth_firewall='Only hidden plant construction and post-run evaluation use case physical truth; controller sees causal measured state and belief.',metrics=['completion','tracking','J_F_task','force','moment','clearance','duration','beta','updates','model_consumption','residual','geometry'],criteria={'A':'Parameters/belief change + reconstructed model change + planner and execution numeric consumption in tested completed cases. Failed cases retained; no arbitrary generalization.','B':'C2, bounded q/dq/ddq/jerk, early changed reference, full safety activation and valid CR12 closure. Unit probes alone insufficient.'},reference_dt_s=.005,command_periods_s=[.005,.01,.02,.05],single_process=True,wall_target_hours=[5,8],hard_cap_hours=10,no_training=True,no_hardware=True))
save('STATE.json',dict(status='RUNNING',phase='HUMAN_SOURCE_AUDIT_AND_QUALIFICATION',started_utc=datetime.now(timezone.utc).isoformat(),branch=git('branch','--show-current'),source_commit=source,next_action='Run inherited four-Human three-arm qualification; implement online acceleration-aware reference after adaptation audit.',committed=False,pushed=False,merged=False))
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/df3a1733-5a16-4098-ad79-4cbf7192b409/已粘贴的文本.txt',D/'USER_REQUEST.txt')
shutil.copy2(__file__,W/'bootstrap.py')
print(json.dumps({'frozen_files':len(files),'cases':case_names,'docs':str(D)}))
