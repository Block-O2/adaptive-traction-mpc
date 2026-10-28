"""Preserve prior closeout, record root-cause evidence, freeze operational repair."""
from pathlib import Path
import json,time,hashlib,shutil,sys,subprocess
import numpy as np
from operational_memory_v3 import chunks
from resource_policy_v2 import POLICY
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';R=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/dagger_anchored_sac_v2';O=S/'results/dagger_anchored_sac_v2'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(L/'PREREGISTRATION.json')==old['config'];assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')]
archive=L/'before_resume_36283';archive.mkdir(exist_ok=False)
for p in L.iterdir():
 if p.is_file():shutil.copy2(p,archive/p.name)
state=json.loads((L/'STATE.json').read_text());assert state['total_online_steps']==36283
flag=json.loads((L/'RESOURCE_PAUSE_FLAG_V2.json').read_text());event=flag['resource_row'];history=[json.loads(x) for x in (L/'RESOURCE_CONTINUATION.jsonl').read_text().splitlines()];before=[x for x in history if x.get('workset_identity')==event['workset_identity'] and event['unix']-100<=x['unix']<=event['unix']]
timeline=[dict(unix=x['unix'],phase=x['lifecycle'],PSS_bytes=x['tree_PSS_bytes'],available_bytes=x['available_bytes'],swap_bytes=x['swap_bytes'],processes=[{k:p.get(k) for k in ('pid','ppid','Rss','Pss','cmd','state')} for p in x['processes']['owned']]) for x in before]
release={str(pid):not Path(f'/proc/{pid}').exists() for pid in event['workset_identity']};assert all(release.values())
fixture={'schema':'test','trace':[{'x':np.arange(8).reshape(2,4),'scalar':np.float64(1.2),'bool':np.bool_(True),'nonfinite':float('nan'),'tuple':(1,2),'nested':{'a':np.int64(4)}} for _ in range(15)]}
def legacy(v):
 if isinstance(v,np.ndarray):return legacy(v.tolist())
 if isinstance(v,np.generic):return legacy(v.item())
 if isinstance(v,dict):return {str(k):legacy(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [legacy(x) for x in v]
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
assert json.loads(''.join(chunks(fixture)))==legacy(fixture)
physical={str(p):sha(p) for p in O.rglob('*') if p.is_file()};sourcehistory=P/'source_history/resume_36283';sourcehistory.mkdir(exist_ok=True)
git=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip(),status=subprocess.check_output(['git','status','--short'],cwd=R,text=True),index_sha256=sha(R/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','diff','--cached','--binary'],cwd=R)).hexdigest())
start=time.time();auth=dict(user_request='Resume exact36283; autonomously diagnose/fix logging/lifecycle, complete50000 and final replays. Scientific and learning semantics frozen. User away; no ordinary engineering confirmation.',collection_start=36283,remaining=13717,total_cap=50000,authorized_unix=start,original_start=state['started_unix'],original_deadline=state['hard_cutoff_unix'],original_deadline_expired=start>state['hard_cutoff_unix'],operational_cutoff_unix=start+12*3600,reason='New explicit continuation overrides expired operational wall stop; no reset of scientific step budget or original elapsed-time record.',scientific_config_sha256=old['config'])
diag=dict(classification='A+C: idle training parent plus evaluation trace logging temporary conversion/string copies; historical data support allocation spike, not proven leak',confirmed=['training parent PSS stable in final interval','evaluation child accounted for final1.55GiB jump','runtime serializer copies complete nested payload then creates full indented JSON string (three calls near finalization)','all old physics/evaluation PIDs exited, no orphan owner'],pending_live_regression='pending25k remaining replays with bounded serializer; verify stable child teardown and exact frozen evaluation contract',historical_timeline=timeline,old_pids_released=release,old_guard=flag,repair='stream same runtime artifact fields without whole-payload conversion/string; serial joined/reaped physics and isolated evaluation; stage-aware resource decisions',semantic_serializer_fixture='PASS',scientific_changes=[],old_lock=old)
for f in (L,D):
 for name,value in [('RESUME_36283_AUTHORIZATION.json',auth),('RESOURCE_ROOT_CAUSE_36283.json',diag),('PRESERVATION_BEFORE_36283.json',dict(physical_files=physical,git=git)),('RESOURCE_POLICY_V2.json',POLICY)]: (f/name).write_text(json.dumps(value,indent=2)+'\n')
 (f/'RESOURCE_PAUSE_FLAG_V2.json').replace(f/'RESOURCE_PAUSE_FLAG_V2_2_before_stream_fix.json')
for p in P.glob('*.py'):
 compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision=POLICY['version'],prior_lock_archived=str(archive/'LOCK.json'))
for f in (L,D):(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print(json.dumps(dict(status='FROZEN',serializer_parity='PASS',old_children_released=release,physical_files_preserved=len(physical),scientific_hash=old['config'],new_resource_policy=POLICY['version'],operational_deadline=auth['operational_cutoff_unix'])))
