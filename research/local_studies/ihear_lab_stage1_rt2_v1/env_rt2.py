from pathlib import Path
import sys, json, hashlib
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G = HERE.parent / 'ihear_lab_stage1g_v1'
BASE = G / 'runs/1794510614855211526/native'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0, str(ROOT/'stages'/stage/'src'))
for stage in ('g','e','d','f'):
    sys.path.append(str(HERE.parent/f'ihear_lab_stage1{stage}_v1'))
sys.path.append(str(HERE.parent/'ihear_lab_stage1b_v1/deps'))
CONTRACT = ROOT/'stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.file_digest(p.open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):
    import numpy as np
    with p.open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, allow_nan=False, default=lambda v: v.tolist() if isinstance(v,np.ndarray) else v.item())
