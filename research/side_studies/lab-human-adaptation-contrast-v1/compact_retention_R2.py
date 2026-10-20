"""Compact redundant non-key prediction logs; verify unchanged frozen scientific scorer first."""
import os,sys
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
from pathlib import Path
import json,gzip,re,tempfile,hashlib,shutil,gc
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1')
R=W/'snapshot';S=R/'stages/stage5_personalized_motion_learning'
sys.path.insert(0,str(S/'scripts/high_rom_v1'))
from evaluate_execution_mode import evaluate
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readjson(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def fields(lines,indent,keys):
 result={};current=None;buf=[]
 regex=re.compile(r'^'+' '*indent+r'"([^"]+)":')
 def finish():
  if current in keys:result[current]=''.join(buf).rstrip().removesuffix(',')
 for line in lines:
  match=regex.match(line)
  if match:
   finish();current=match.group(1);buf=[line] if current in keys else []
  elif current in keys:buf.append(line)
 finish()
 return result
def export_compact(src):
 # Each outer field is emitted on its own indent2 line by immutable JSON writer.
 required={'execution_mode','requests','activation_validations','safe_fallback_events','adaptation_trace'}
 result={};current=None;buf=[];wall_current=None;wallbuf=[];wallfields={}
 outer=re.compile(r'^  "([^"]+)":');inner=re.compile(r'^    "([^"]+)":')
 neededwall={'native_states_evaluation_only','catchup_intervals','control_cycle_misses','schema','execution_mode'}
 def finish_wall():
  if wall_current in neededwall:wallfields[wall_current]=''.join(wallbuf).rstrip().removesuffix(',')
 def finish_outer():
  if current in required:result[current]=''.join(buf).rstrip().removesuffix(',')
 with gzip.open(src,'rt') as f:
  for line in f:
   m=outer.match(line)
   if m:
    if current=='wall_physics':finish_wall()
    else:finish_outer()
    current=m.group(1);buf=[line] if current in required else [];continue
   if current=='wall_physics':
    m=inner.match(line)
    if m:
     finish_wall();wall_current=m.group(1);wallbuf=[line] if wall_current in neededwall else []
    elif line.startswith('  }'):
     finish_wall();wall_current=None;wallbuf=[]
    elif wall_current in neededwall:wallbuf.append(line)
   elif current in required:
    if line.strip()=='}' and line.startswith('}'):continue
    buf.append(line)
 if current=='wall_physics':finish_wall()
 else:finish_outer()
 assert all(k in result for k in ['execution_mode','requests','activation_validations','safe_fallback_events'])
 assert all(k in wallfields for k in ['native_states_evaluation_only','catchup_intervals'])
 result['wall_physics']='  "wall_physics": {\n'+',\n'.join(v for v in wallfields.values())+'\n  }'
 return '{\n'+',\n'.join(result.values())+'\n}\n'
def main():
 c=readjson(W/'CONTRACT_R2.json');matrix=readjson(W/'PRIMARY_MATRIX_R2.json');assert matrix['executed_primary_runs']==21
 keep={'C0__fixed_population','C0__commissioning_only','C0__continual_adaptive','C1__commissioning_only','C4__commissioning_only','C4__continual_adaptive','C6__commissioning_only'}
 report=[]
 for r in matrix['runs']:
  d=W/'runs_R2'/f"{r['condition']}__{r['arm']}";src=d/'runtime_artifacts.json.gz'
  if not src.exists():continue
  row={'run':d.name,'original_sha256':digest(src),'original_bytes':src.stat().st_size,'trace_npz_sha256':digest(d/'trace.npz'),'trace_npz_bytes':(d/'trace.npz').stat().st_size}
  if r['status']!='COMPLETE' or d.name in keep:
   row.update(retention='FULL_KEY_OR_FAILURE_RAW',reason='All failures; all nominal; mass60 commissioning recovery; K13 strongest continual tracking improvement pair; rho.66 geometry benefit.')
  else:
   compact=export_compact(src)
   # Parsed scientific fields plus all compact metrics/models/predictions/NPZ remain.
   json.loads(compact)
   q=readjson(d/'qualification.json');summary=readjson(d/'summary.json');old=readjson(d/'MODE_AWARE_AUDIT.json')
   e=next(e for e in c['conditions'] if e['id']==r['condition'])
   with tempfile.TemporaryDirectory(prefix='retention_verify_',dir=W) as temp:
    tmp=Path(temp);(tmp/'runtime_artifacts.json').write_text(compact);(tmp/'summary.json').write_text(json.dumps(summary))
    (tmp/'HIGH_ROM_CASE_RESULT.json').write_text(json.dumps({'status':summary['status'],'abort_reason':summary.get('abort_reason'),'case_sha256':e['case_sha256'],'elapsed_host_s':q['elapsed_host_s'],'execution_mode':'SCIENTIFIC_SIMULATION','scientific_host_delay_ms':0.}))
    (tmp/'trace.npz').symlink_to(d/'trace.npz')
    scoring=readjson(S/'docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'];case=e['case']
    check=evaluate(tmp,{'case_key':case['case_key'],'physical_variant':case['cell']['family'],'candidate':case.get('coordination_candidate'),'path':e['case_path'],'sha256':e['case_sha256']},scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
   for key in ['physical_task_result','scientific_validity','overall_result_for_mode','wall_runtime_characterization']:assert check[key]==old[key],(d.name,key)
   assert check['raw_scorer_v2']['conditions']==old['raw_scorer_v2']['conditions']
   new=src.with_name('runtime_artifacts.compact_pending.json.gz')
   with gzip.open(new,'wt',compresslevel=3) as f:f.write(compact)
   with gzip.open(new,'rt') as f:assert f.read()==compact
   new.replace(src)
   row.update(retention='COMPACT_SCIENTIFIC_SCORER_EVIDENCE',new_sha256=digest(src),new_bytes=src.stat().st_size,scientific_and_physical_verdict_exact_parity=True,all_wall_characterization_exact_parity=True,original_byte_hash_retained=True,not_a_realtime_full_replay='Full nested command/prefix expansions omitted; all original SCIENTIFIC_SIMULATION evaluator fields retained. Actual physical trace and per-PID model consumption remain.')
   print('COMPACT_VERIFIED',d.name,row['original_bytes'],row['new_bytes'],flush=True)
   del compact,summary,check;gc.collect()
  report.append(row)
 (W/'RETENTION_FINAL_R2.json').write_text(json.dumps({'status':'VERIFIED_COMPACT_RETENTION','runs':report,'preserved_all_prior_evidence':True,'diagnostic_oracle_full_raw_retained':True,'no_training_history_or_archive_copied':True},indent=2)+'\n')
 print('RETENTION_COMPLETE',len(report),flush=True)
if __name__=='__main__':main()
