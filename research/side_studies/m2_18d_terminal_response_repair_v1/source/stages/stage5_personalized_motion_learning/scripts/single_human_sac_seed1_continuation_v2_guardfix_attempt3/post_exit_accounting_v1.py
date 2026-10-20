"""Read-only post-exit accounting; no SAC, Torch or simulation imports."""
from pathlib import Path
import importlib.util, json, os, shutil, subprocess, time

W = Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
S = Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1/source/stages/stage5_personalized_motion_learning')
D = S / 'docs/single_human_sac_seed1_continuation_v2_guardfix_attempt3'
L = W / 'single_human_sac_seed1_continuation/output_attempt3'
spec = importlib.util.spec_from_file_location('memory_readonly', W / 'single_human_sac_memory/memory_test_v1.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
processes = m.processes()
live = []
for path in Path('/proc').iterdir():
    if not path.name.isdigit() or int(path.name) == os.getpid():
        continue
    try:
        argv = (path / 'cmdline').read_bytes().split(b'\0')
        if argv and b'python' in argv[0] and any(b'continue_seed1_v' in arg for arg in argv[1:]):
            live.append({'pid': int(path.name), 'argv': [arg.decode(errors='replace') for arg in argv if arg]})
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
mem = m.memfile('/proc/meminfo')
win = m.windows()
row = dict(unix=time.time(), phase='after_all_training_processes_exited',
           windows=win, wsl=mem, swap_used_bytes=mem['SwapTotal']-mem['SwapFree'],
           live_training_processes=live, observer_processes=processes,
           torch_gpu_allocated_reserved='not applicable: SAC process exited; Torch not loaded',
           nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),
           memory_pressure=Path('/proc/pressure/memory').read_text())
assert not live, live
for folder in (D, L):
    (folder / 'POST_EXIT_RESOURCE_ACCOUNTING.json').write_text(json.dumps(row, indent=2, sort_keys=True)+'\n')
shutil.copy2(Path(__file__), S / 'scripts/single_human_sac_seed1_continuation_v2_guardfix_attempt3' / Path(__file__).name)
print(json.dumps(dict(training_processes=len(live), swap_mib=row['swap_used_bytes']/2**20,
                      windows_available_gib=win['AvailableBytes']/2**30,
                      windows_commit_headroom_gib=(win['CommitLimit']-win['CommittedBytes'])/2**30,
                      wsl_available_gib=mem['MemAvailable']/2**30, wsl_cache_gib=mem['Cached']/2**30)))
