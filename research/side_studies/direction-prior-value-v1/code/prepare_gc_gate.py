from freeze import *
def main():
 path=STUDY/'queue/014_streaming_fork_v2_regression.json';events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];assert not any(r['event']=='START' and r['id']==path.stem for r in events)
 old=json.loads(path.read_text());save(STUDY/'source_history/014_before_late_gate.json',dict(request=old,sha256=sha(path)))
 old.update(targets=[['OUTBOUND',0],['RETURN',1]],operational_gate='pre-snapshot collection only; early and late B forks and distinct branch archives');save(path,old)
 save(STUDY/'PLAN_AMENDMENT_07_PRE_SNAPSHOT_LIFECYCLE.json',dict(unix=time.time(),before_heldout_tests=True,original_start_unix=1791222386,physics_changes=[],safety_changes=[],B_changes=[],changes=['gc.collect only BEFORE frozen snapshot, never between before/after fork checks; no malloc_trim','stage memory evidence before/after collection and child manifest/value','route logging-only persist_runtime_artifacts to env.episode_dir after fork; native output_dir argument was inherited parent causing interrupt archive collision','014 adds late RETURN1 B branch; exact B costs and full fork hash must pass before resumed development'],earlier_artifact_limitation='Early child native runtime_artifacts routed to parent directory and overwritten by parent; unique child trace/summary/DATA retained, no claim that lost child runtime artifacts recovered',extra_gate_attempts=1))
 print('EARLY_LATE_GC_GATE_PREPARED')
if __name__=='__main__':main()
