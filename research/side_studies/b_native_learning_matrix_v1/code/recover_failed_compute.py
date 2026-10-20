"""Bounded scalar recovery; never expand archived sensor histories."""
from task_bootstrap import *
import gzip,re,os

def main():
 path=STUDY/'COMPUTE_CORRECTIONS.jsonl'
 seen={json.loads(line)['id'] for line in path.read_text().splitlines()} if path.exists() else set()
 rows=[]
 for id in ('000_original_B','001_zero_interface'):
  if id not in seen:rows.append(dict(id=id,actual_new_simulation_s=0,actual_new_native_steps=0,main_model_calls=0,native_worker_model_calls_separate=0,basis='saved traceback: stdlib inspect shadowing during numpy/scipy import before any environment or physics initialization'))
 for id,anchor in (('parent_dev_0_RETURN_1_candidate2','RETURN_1'),('parent_dev_0_OUTBOUND_4_candidate2','OUTBOUND_4')):
  p=STUDY/'source/results'/id/'runtime_artifacts.json.gz'
  if not p.exists() or id in seen:continue
  fields={};tail=''
  with gzip.open(p,'rt') as f:
   for chunk in iter(lambda:f.read(262144),''):
    block=tail+chunk
    for key in ('physics_elapsed_s','origin_physics_s','native_dt_s'):
     hits=re.findall('"'+key+'":([-+0-9.eE]+)',block)
     if hits:fields[key]=float(hits[-1])
    tail=block[-200:]
  sibling=json.loads((STUDY/'output'/('parent_dev_0_'+anchor+'_candidate0_DATA.json')).read_text())
  prefix=sibling['child']['physical_time_at_fork'];dt=fields['native_dt_s'];total=fields['origin_physics_s']+fields['physics_elapsed_s']
  assert prefix<total and dt==.00025
  rows.append(dict(id=id,actual_new_simulation_s=total-prefix,actual_new_native_steps=round(total/dt)-sibling['child']['physics_step_at_fork'],main_model_calls=None,native_worker_model_calls_separate=None,basis='streaming scalar physics_elapsed_s/native_dt_s recovered from verified compressed all-outcome runtime artifact; identical snapshot hash from successful sibling provides exact inherited physical prefix',snapshot_hash=sibling['child']['snapshot_hash'],runtime_artifact_sha256=sha(p),model_count_unknown=True))
 for row in rows:
  row['unix']=time.time()
  with path.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 print('CORRECTIONS_APPENDED',len(rows))
if __name__=='__main__':main()
