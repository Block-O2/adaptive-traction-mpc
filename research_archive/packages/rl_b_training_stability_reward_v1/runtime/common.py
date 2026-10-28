"""Paths and provenance for read-only reuse of the actual native source."""
from pathlib import Path
import os, sys, json, hashlib
ROOT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(ROOT/'cache'/'matplotlib')
SOURCE=(ROOT/'source').resolve()
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0,str(SOURCE/'stages'/stage/'src'))
STAGE=SOURCE/'stages/stage5_personalized_motion_learning'
def load_config():
    case_path=STAGE/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'
    historical=json.loads((STAGE/'docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json').read_text())
    options_path=SOURCE/historical['options_path']
    options=json.loads(options_path.read_text())
    if os.environ.get('IHEAR_THREAD_PLANNER')=='1':
        # Existing source option, used only for explicitly labelled scientific
        # simulation memory tests. Snapshot serialization and frozen epoch stay.
        options['planner_process_worker']=False
    return json.loads(case_path.read_text()),options
def clean(x):
    import numpy as np
    from dataclasses import asdict,is_dataclass
    if is_dataclass(x):return clean(asdict(x))
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,Path):return str(x)
    return x
def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(value),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def digest(x):return hashlib.sha256(json.dumps(clean(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()
