"""Read-only dispatch/source retention and single-owner audit, no replay."""
from task_bootstrap import *
from collections import Counter,defaultdict

def main():
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if x.strip()]
 starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END'];start_by={e['id']:e for e in starts};end_by={e['id']:e for e in ends};issues=[];rows=[];retained=defaultdict(list);hash_cache={}
 def digest(p):
  key=str(p)
  if key not in hash_cache:hash_cache[key]=sha(p)
  return hash_cache[key]
 for root in (STUDY/'code',STUDY/'code_history'):
  for p in root.rglob('*.py'):retained[(p.name,digest(p))].append(str(p))
 manifests={digest(p):p for p in (STUDY/'code_history').glob('*/CODE_MANIFEST.json')};manifests[digest(STUDY/'CODE_MANIFEST.json')]=STUDY/'CODE_MANIFEST.json'
 qhash=digest(STUDY/'weights/frozen_Q_v1/weights.npz');source_hash=digest(STUDY/'SOURCE.json')
 for e in starts:
  id=e['id'];dispatch_cfg=e.get('config',{});cfg=dispatch_cfg.get('consecutive_requests',[dispatch_cfg])[0];local=[];warnings=[];parent=e.get('same_process_parent');end=end_by.get(id);p=STUDY/'queue'/(id+'.json')
  if not p.exists():p=STUDY/'inputs'/(id+'.json')
  declared_input=e.get('input_sha256',e.get('input_hash'));input_exact=p.exists() and (declared_input is None or digest(p)==declared_input)
  if not input_exact:local.append('INPUT_BYTES_OR_HASH_MISMATCH')
  result_path=STUDY/'output'/(id+'_RESULT.json');result=json.loads(result_path.read_text()) if result_path.exists() else {};result_cfg=result.get('inputs',{})
  differences=[k for k in sorted(set(cfg)|set(result_cfg)) if cfg.get(k)!=result_cfg.get(k)]
  if differences:local.append('RESULT_CONFIG_DIFFERS_FROM_START')
  if cfg.get('weights_sha256')!=qhash:local.append('REGISTERED_Q_HASH_DIFFERS')
  if cfg.get('source_manifest_sha256') not in manifests:local.append('REGISTERED_CODE_MANIFEST_BYTES_NOT_LOCATED')
  sources=[];unretained=[]
  for path,expected in cfg.get('algorithm_sources',{}).items():
   psource=Path(path);current=psource.exists() and digest(psource)==expected;copies=[str(psource)] if current else retained.get((psource.name,expected),[])
   sources.append(dict(path=path,declared_sha256=expected,current_equal=current,retained_byte_copies=copies[:2],retained=bool(copies)))
   if not copies:unretained.append(dict(path=path,sha256=expected))
  if unretained:warnings.append('DECLARED_ACTOR_BYTES_NOT_LOCATED')
  owner=start_by.get(parent,e);manifest_hash=owner.get('code_manifest_sha256');mp=manifests.get(manifest_hash);manifest=json.loads(mp.read_text()) if mp else {};manifest_mismatch=[path for path,expected in cfg.get('algorithm_sources',{}).items() if manifest.get(path)!=expected]
  if manifest_hash and not mp:warnings.append('OWNER_CODE_MANIFEST_BYTES_NOT_LOCATED')
  if manifest_mismatch:warnings.append('GENERAL_CODE_MANIFEST_DIFFERS_FROM_VERSION_REGISTRATION')
  row=dict(id=id,status='FAIL' if local else ('PASS_WITH_RETENTION_LIMITATIONS' if warnings else 'PASS'),issues=local,warnings=warnings,input_sha256=declared_input,input_hash_exact=input_exact,result_config_difference_keys=differences,result_cfg_scope='first explicitly registered episode of wrapper' if 'consecutive_requests' in dispatch_cfg else 'direct dispatch config',result_sha256=digest(result_path) if result_path.exists() else None,registered_Q_equal=cfg.get('weights_sha256')==qhash,registered_code_manifest_retained=cfg.get('source_manifest_sha256') in manifests,registered_code_manifest_sha256=cfg.get('source_manifest_sha256'),owner_id=owner['id'],owner_code_manifest_sha256=manifest_hash,owner_code_manifest_retained=bool(mp),general_manifest_registration_differences=manifest_mismatch,declared_sources=sources,unretained_declared_actor_bytes=unretained,source_retention_is_not_runtime_module_attestation=True)
  if local:issues.append(dict(id=id,issues=local))
  rows.append(row)
 top=[(e['unix'],end_by[e['id']]['unix'],e['id']) for e in starts if not e.get('same_process_parent') and e['id'] in end_by];top.sort();overlaps=[]
 for a,b in zip(top,top[1:]):
  if a[1]>b[0]:overlaps.append(dict(first=a[2],second=b[2],overlap_seconds=a[1]-b[0]))
 children=[]
 for e in starts:
  parent=e.get('same_process_parent')
  if parent:
   enclosed=parent in start_by and parent in end_by and e['id'] in end_by and start_by[parent]['unix']<=e['unix']<=end_by[e['id']]['unix']<=end_by[parent]['unix']
   children.append(dict(id=e['id'],parent=parent,enclosed_by_owner_wall=enclosed))
   if not enclosed:issues.append(dict(id=e['id'],issues=['CHILD_NOT_ENCLOSED_BY_OWNER_WALL']))
 if overlaps:issues.append(dict(id='OWNER_WALL',issues=['OVERLAPPING_TOP_LEVEL_PHYSICS_OWNER'],rows=overlaps))
 duplicates=dict(START=[id for id,n in Counter(e['id'] for e in starts).items() if n!=1],END=[id for id,n in Counter(e['id'] for e in ends).items() if n!=1])
 if any(duplicates.values()):issues.append(dict(id='EVENT_IDS',issues=['DUPLICATE_ATTEMPT_IDS'],rows=duplicates))
 out=dict(status='FAIL' if issues else ('PASS_WITH_RETENTION_LIMITATIONS' if any(r['warnings'] for r in rows) else 'PASS'),attempts=len(starts),ended=len(ends),rows=rows,issues=issues,top_level_owners=len(top),top_level_overlap_rows=overlaps,same_owner_children=children,duplicate_event_ids=duplicates,Q_sha256=qhash,control_source_manifest_sha256=source_hash,physics_added=0,runtime_attestation_limit='Matching declared bytes and retained registration manifests establish reproducibility, not a per-module import-time attestation. General CODE_MANIFEST may be older than a directly installed worker route; such mismatches are preserved explicitly. Current files are never relabeled as historical execution bytes.',unique_python_byte_variants=len(retained),unretained_declared_sources=sum(len(r['unretained_declared_actor_bytes']) for r in rows),general_manifest_registration_mismatch_attempts=sum(bool(r['general_manifest_registration_differences']) for r in rows))
 target=STUDY/'reports/SOURCE_CLOSURE_AUDIT.json'
 if target.exists():shutil.copy2(target,STUDY/'reports'/('SOURCE_CLOSURE_AUDIT_HISTORY_'+sha(target)+'.json'))
 out['registration_contract']='prepare_tasks.enqueue defines source_manifest_sha256 as the CODE_MANIFEST file hash, not SOURCE.json hash. For wrapper owners, RESULT inputs are its explicit first consecutive_requests entry; child STARTs have direct per-episode configs. No logged input/result is rewritten.'
 save(target,out);print(json.dumps({k:out[k] for k in ('status','attempts','ended','issues','top_level_owners','top_level_overlap_rows','unique_python_byte_variants','unretained_declared_sources','general_manifest_registration_mismatch_attempts')}))
if __name__=='__main__':main()
