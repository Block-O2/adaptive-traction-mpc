"""Prepare an exact runtime plan replica before the inherited harness imports it."""
from pathlib import Path
import json,sys,hashlib,time,os
P=Path(__file__).resolve().parents[1];src=P/sys.argv[1];raw=src.read_bytes();c=json.loads(raw);g=c['group']
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert g.replace('_','').isalnum()
assert not (P/'owned'/(g+'_SUPERVISOR.json')).exists(),'NEVER_RESTART_EXISTING_GROUP'
assert not (P/'jobs'/g/'SOURCE_MANIFEST.json').exists(),'EXISTING_EXECUTION_IDENTITY'
assert time.time()<json.loads((P/'ACTIVATION.json').read_text())['deadline_unix']-600
for rel,h in c.get('frozen_artifacts',{}).items():assert sha(P/rel)==h,'FROZEN_ARTIFACT_CHANGED:'+rel
assert sha(P/c['case_path'])==c['case_sha256'],'CASE_IDENTITY_MISMATCH'
for rel in ['runtime/RUN_PLAN.json','runtime/MOTION_ACCEPTANCE_PROTOCOL.json','source/'+c['worker'],'runtime/control/campaign_v6.py']:
 assert (P/rel).is_file(),'MISSING_EXECUTION_DEPENDENCY:'+rel
dest=P/'runtime'/(g+'_TEST_PLAN.json')
if dest.exists():assert dest.read_bytes()==raw,'IMMUTABLE_RUNTIME_PLAN_CONFLICT'
else:
 tmp=dest.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(dest)
assert sha(dest)==sha(src)
out=P/'audit'/(g+'_PRELAUNCH.json');assert not out.exists()
out.write_text(json.dumps({'status':'PASS','created_unix':time.time(),'group':g,'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'config_sha256':sha(src),'exact_runtime_plan_sha256':sha(dest),'source_sha256':sha(Path(__file__)),'frozen_artifacts':c.get('frozen_artifacts',{}),'new_physics':0},indent=2)+'\n')
print('PRELAUNCH_IDENTITY_PASS',g,sha(dest))
