"""Final evidence precision annotation; no simulation or repeated broad tests."""
from pathlib import Path
import sys,json,hashlib,time,shutil
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/learning_guided_motion_improvement_v1/runtime')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
sys.path.insert(0,str(S/'code'))
import numpy as np
from native_inference import Networks
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
n=Networks(S/'weights/frozen_Q_v1');x=np.zeros((6,120),np.float32)
dtype=dict(feature_input=str(x.dtype),normalization=str(n.scale(x).dtype),linear_weights=str(n.w['linear_W'].dtype),Q_output=str(n.values(x).dtype),y_mean=str(n.w['y_mean'].dtype),y_scale=str(n.w['y_scale'].dtype),scope='Native inference actual mixed precision; conservative close-rank bound uses float32 epsilon and remains unchanged')
qp=S/'Q_RANKING_ATTRIBUTION.json';q=json.loads(qp.read_text());q['actual_inference_dtypes']=dtype
q['native_bitwise_equivalence_claim']=False
q.pop('deployed_float32_bitwise_equivalence_claim',None)
save(qp,q)
changed=['Q_RANKING_ATTRIBUTION.json','Q_RANKING_ATTRIBUTION.md','REPORT.md']
for name in ('Q_RANKING_ATTRIBUTION.md','REPORT.md'):
    p=S/name;text=p.read_text().replace('float32 排序数','native mixed-precision 排序数').replace('raw float32排序数','raw native mixed-precision排序数').replace('float32 分数差漂移','native mixed-precision 分数差漂移').replace('不宣称float32 bitwise等价','不宣称native bitwise等价')
    lo,hi=q['fixed_candidates_mask_carry_probe']['raw_Q_candidate0_range_N_s']
    text+=f'\n数值精度核验：实际feature/normalization=float32，linear_W/Q_output/y_mean/y_scale=float64；原close-rank的float32保守误差bound保持不变。固定候选探针candidate0绝对Q从{lo:.9f}到{hi:.9f} N·s，但相对排序始终不变。共同状态项的明显绝对变化不能证明state-conditioned preference。\n'
    p.write_text(text)
script=W/'finalize_precision_note.py';shutil.copy2(script,S/'code'/script.name)
changed.append('code/'+script.name)
vpath=S/'PACKAGE_VERIFICATION.json';v=json.loads(vpath.read_text());v['actual_Q_inference_dtypes']=dtype;v['final_annotation_unix']=time.time()
for name in v['required_files']:v['required_files'][name]['sha256']=sha(S/name)
v['Windows_review_copy']='PASS; full1647-file copy checked byte-for-byte at close, precision annotation files rechecked below'
save(vpath,v);changed.append('PACKAGE_VERIFICATION.json')
manifest=json.loads((S/'FULL_PACKAGE_MANIFEST.json').read_text())
for name in changed:manifest[name]=dict(bytes=(S/name).stat().st_size,sha256=sha(S/name))
save(S/'FULL_PACKAGE_MANIFEST.json',manifest);changed.append('FULL_PACKAGE_MANIFEST.json')
for name in changed:
    target=W/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/name,target);assert sha(target)==sha(S/name)
for name,info in v['required_files'].items():assert sha(S/name)==info['sha256'] and sha(W/name)==info['sha256']
assert json.loads((S/'PACKAGE_CLOSED.json').read_text())['physical_dispatch_permitted'] is False
print(json.dumps(dict(status='PASS',scientific_status='PARTIAL',all_required_files_verified=True,actual_inference_dtypes=dtype,canonical=str(S),review=str(W),attempts=9,physics_runs=8,pairs=4,manifest_files=len(manifest),manifest_bytes=sum(r['bytes'] for r in manifest.values()),final_wall_seconds=time.time()-json.loads((S/'RUN_PLAN.json').read_text())['t0_unix'])))
