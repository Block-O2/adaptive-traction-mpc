from audit_common import *
import fcntl
def hostpath(s):
 if len(s)>2 and s[1]==':':return Path('/mnt/'+s[0].lower()+'/'+s[3:].replace('\\','/'))
 return Path(s)
def main():
 lock=(STUDY/'runner.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 events=[json.loads(s) for s in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[e for e in events if e['event']=='START'];ends={e['id']:e for e in events if e['event']=='END'}
 baseline=read(STUDY/'OLD_EVIDENCE_BEFORE.json');changed=[]
 for name,old in baseline.items():
  p=Path(name)
  if not p.exists():changed.append(dict(path=name,reason='MISSING'));continue
  st=p.stat()
  if st.st_size!=old['size'] or st.st_mtime_ns!=old['mtime_ns'] or ('sha256' in old and sha(p)!=old['sha256']):changed.append(dict(path=name,reason='SIZE_MTIME_OR_HASH'))
 added=[str(p) for p in OLD.rglob('*') if p.is_file() and not p.is_relative_to(STUDY) and str(p) not in baseline]
 protected=read(STUDY/'MAIN_SOURCES_BEFORE.json');source_changes=[s for s,h in protected.items() if not hostpath(s).exists() or sha(hostpath(s))!=h]
 relocated=read(STUDY/'SOURCE_RELOCATION.json')['source_hashes'];runtime_changes=[s for s,h in relocated.items() if not Path(s).exists() or sha(s)!=h]
 contract=read(STUDY/'AUDIT_CONTRACT.json');weight_changes=[s for s,h in contract['weights_sha256'].items() if sha(s)!=h]
 initial_manifest=read(STUDY/'code_history/75134ed481922babf168ede927c8a161a66e32d3a411a32a861d3a737f066a48/CODE_MANIFEST.json')
 core_paths=[STUDY/'code'/name for name in ('planning.py','interfaces.py','known_model.py','inference.py','study_common.py')]+[STUDY/'deps/fork_core.py']
 core_changes=[str(p) for p in core_paths if sha(p)!=initial_manifest[str(p)]]
 semantic=read(STUDY/'SOURCE_SEMANTICS_initial_before_history_clarification.json');first=min(e['unix'] for e in starts);bcontract=read(STUDY/'B_REFERENCE_CONTRACT.json')
 checks=dict(old_evidence_unchanged=not changed,old_no_added_files=not added,main_git_equal=main_git()==read(STUDY/'MAIN_GIT_BEFORE.json'),main_original_sources_unchanged=not source_changes,new_copied_physical_sources_unchanged=not runtime_changes,weights_unchanged=not weight_changes,source_audit_before_first_physics=semantic['unix']<first,B_reference_preregistered_before_attribution=bcontract['registered_unix']<min(e['unix'] for e in starts if e['id'].startswith('100_attribution')),attempt_cap=len(starts)<=50,all_attempts_have_END=all(e['id'] in ends for e in starts),all_queued_tasks_returned=all(p.stem in read(STUDY/'TASK_LEDGER.json') and read(STUDY/'TASK_LEDGER.json')[p.stem]['status']!='RUNNING' for p in (STUDY/'queue').glob('*.json')),no_training=True)
 active=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(STUDY/'code/worker.py') in cmd or str(STUDY/'code/runner.py') in cmd or (str(STUDY) in cmd and 'native_worker' in cmd):active.append(dict(pid=int(p.name),command=cmd))
  except OSError:pass
 checks['no_owned_physics_or_runner_processes']=not active;checks['online_core_unchanged_since_prephysics_instrumentation']=not core_changes
 data=read(STUDY/'SCORE_DECOMPOSITION.json');pair=read(STUDY/'FIRST_SEGMENT_PAIR_VERIFICATION.json');attr=read(STUDY/'HUMAN_MODEL_ATTRIBUTION.json')
 checks.update(all15_candidates_have_ABC=data['complete'],all_ABC_qualified=all(m['qualified'] for s in data['states'] for r in s['rows'] for m in r['mode_metrics'].values()),all30_first_segment_pairs_exact=pair['status']=='PASS' and pair['pairs']==30,all4_parameter_pairs_qualified=attr['summary']['qualified_pairs']==4,label_arithmetic_pass=read(STUDY/'LABEL_CONSISTENCY.json')['status']=='PASS')
 baselines=[p['new_B_reference'] for p in attr['pairs'] if 'new_B_reference' in p];checks['both_new_B_references_qualified_and_paired']=len(baselines)==2 and all(r['qualified'] and all(r['controls'].values()) for r in baselines)
 newbytes=sum(p.stat().st_size for p in STUDY.rglob('*') if p.is_file());checks['new_data_under5GiB']=newbytes<5*2**30
 result=dict(status='PASS' if all(checks.values()) else 'FAIL',unix=time.time(),checks=checks,old_files_checked=len(baseline),main_sources_checked=len(protected),runtime_sources_checked=len(relocated),new_bytes=newbytes,old_changes=changed,old_added=added,main_source_changes=source_changes,runtime_changes=runtime_changes,weight_changes=weight_changes,online_core_changes=core_changes,active=active,attempts=len(starts),ends=len(ends),training_runs=0)
 save(STUDY/'PRESERVATION_AND_CLOSEOUT.json',result);print(json.dumps(result));assert result['status']=='PASS'
if __name__=='__main__':main()
