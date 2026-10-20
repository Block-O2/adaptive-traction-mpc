"""Complete four unexecuted historical support artifacts after physical closeout."""
from pathlib import Path
import json,hashlib,shutil,time
P=Path(__file__).resolve().parents[1];H=P.parent/'ihear_overnight_research_retrospective_v1'
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
assert sum(x['event']=='START' for x in events)==sum(x['event']=='END' for x in events)==15
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
declared=json.loads((H/'CODE_MANIFEST.json').read_text());copied=[]
names=['build/fast_native.cpython-310-x86_64-linux-gnu.so','build/temp/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/native/fast_native.o','native/build_native.py','native/fast_native.cpp']
for n in names:
 assert not (P/n).exists(),n
 assert sha(H/n)==declared[n]
 (P/n).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(H/n,P/n);copied.append(dict(path=n,sha256=sha(P/n),historical_source=str(H/n)))
out=dict(unix=time.time(),stage='post-physics final archival-closure audit',error='Initial full 1376-entry source-closure verification failed because four native support files were not copied with source/code/deps/weights',copied=copied,execution_manifest_changed=False,new_physics_starts=0,physics_results_changed=False,scientific_change=False,historical_write=False,scope='complete archival manifest, not a new executable runtime version or retroactive claim that these files existed before START',entrypoint_audit='study_common.run uses runtime_coordination_residual_v2 plus streaming_reuse/operational_memory serializer; it does not call native_geometry/native_quintic/native_small_kernels.install. The separately copied source _prefix_native Linux extension is in the original execution manifest. fast_native support belongs to dormant Native/host optimization helpers; no host/LEVEL2 qualification claimed.',limitation='complete runtime module list after every physical END was not captured; no claim that preflight imports alone prove all late imports',initial_code='audit/closeout_initial.py')
(P/'audit/CLOSEOUT_INITIAL_FAILURE_AND_REPAIR.json').write_text(json.dumps(out,indent=2)+'\n')
x=json.loads((P/'audit/ENGINEERING_EVENTS.json').read_text());x['rows'].append(out);(P/'audit/ENGINEERING_EVENTS.json').write_text(json.dumps(x,indent=2)+'\n')
manifest={n:sha(P/n) for n in declared}
(P/'FINAL_SOURCE_CLOSURE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,late_copied_support=copied,prephysical_manifest='EXECUTION_CODE_MANIFEST.json',prephysical_manifest_preserved=True),indent=2)+'\n')
print(json.dumps(dict(status='ARCHIVAL_CLOSURE_REPAIRED',copied=len(copied),new_physical_starts=0)))
