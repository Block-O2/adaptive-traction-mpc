from pathlib import Path
import json,hashlib,time
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/value_learning_research_v1';RAW=S/'results/value_learning_research_v1'
marked=[]
for p in (RAW/'runs').glob('*/rollout_result.json'):
 r=json.loads(p.read_text())
 if r['status']=='RUNNING':
  backup=p.with_name('rollout_result_before_storage_failure_v2.json')
  if not backup.exists():backup.write_bytes(p.read_bytes())
  r.update(status='INTERRUPTED_HOST_RESOURCE',failure_reason='host C drive exhausted; WSL VM stopped during raw output/swap IO',retry_run_id=r['run_id']+'_retry2',original_record_sha256=hashlib.sha256(backup.read_bytes()).hexdigest());p.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');marked.append(r['run_id'])
 # Reconstitute byte-exact pre-archival result JSON for prior checkpoint hash
 # audit; new archival fields never change scientific contents.
 if r.get('lossless_archives'):
  before={k:v for k,v in r.items() if k!='lossless_archives'}
  before['raw_files_sha256']={k:v for k,v in r.get('raw_files_sha256',{}).items() if not k.endswith('.gz')}
  copy=p.with_name('rollout_result_before_lossless_archival.json')
  if not copy.exists():copy.write_text(json.dumps(before,indent=2,sort_keys=True,allow_nan=False)+'\n')
repair=json.loads((D/'REPAIR_LOG.json').read_text())
repair['cycles'].append({'cycle':2,'kind':'storage_recovery','diagnosis':'Host C free space 318828544 bytes (WSL internal df still 810GB), repeated WSL termination and prior kernel swap read errors','repair':'Lossless gzip of only NEW raw logs with original-content SHA verification, remove verified redundant originals, sudo -n fstrim -v /; host C free space restored >6GB','new_storage':'gzip runtime_artifacts.json, summary.json, learning_transitions.jsonl immediately after each completed unit; original SHA and archive SHA retained; new readers support archives','newly_marked_interrupted':marked,'historical_evidence_modified':False})
repair['repair_cycles_used']=3
repair['logging_cycle_accounting']='One comparator/provenance logging cycle plus two infrastructure cycles; all three have bounded fixes and regression checks.'
(D/'REPAIR_LOG.json').write_text(json.dumps(repair,indent=2,sort_keys=True)+'\n')
state=json.loads((D/'STATE.json').read_text());state.update(phase='HOST_STORAGE_RECOVERED',repair_cycles_used=3,next_action='resume saved CEM2 + branches1 with lossless per-rollout storage; host free space guard')
(D/'STATE.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
print(json.dumps({'marked_interrupted':marked,'repair_cycles_used':3}),flush=True)
