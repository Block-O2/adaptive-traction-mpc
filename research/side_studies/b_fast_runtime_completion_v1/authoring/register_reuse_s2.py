from pathlib import Path
import json,time,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');base=json.loads((S/'queue/048_N13_C2b_host.json').read_text());configs=[]
for n in range(63,67):
 configs.append(base|dict(id=f'{n:03d}_N13_S2_REUSE4_{n-62}',seed=2026100700+n,fast_version=base['fast_version']+'_S2',dependencies=['062_N13_S2_science_nominal'],required_gates=['versions/062_N13_S2_science_nominal_SCI_GATE.json','output/METADATA_REUSE_LOCAL_REGRESSION.json','output/STREAM_REUSE_LOCAL_REGRESSION.json'],series='independent_runtime_diagnostic'))
out=dict(id='N13_S2_REUSE4',same_interpreter=True,configs=configs,registered_unix=time.time(),purpose='Complete4 same-interpreter full tasks after exact serializer AND actual-mode evaluator metadata idempotence; unchanged physical/math/task/safety checks.',prior_preserved_failures=['058_serializer_repeat_install','061_post_physics_mode_metadata_repeat_install'],physical_session_continuous=False)
p=S/'queue/N13_S2_REUSE4.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n')
dest=S/'versions/N13_S2_COHORT_CODE';assert not dest.exists();dest.mkdir()
for root in ('code','native','build'):shutil.copytree(S/root,dest/root,ignore=shutil.ignore_patterns('__pycache__'))
(dest/'MANIFEST.json').write_text(json.dumps({str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()},indent=2)+'\n')
with (S/'PROGRESS.md').open('a') as f:f.write('\nSCI059 S1 bit-exact. REUSE S1 run060 fulltask complete;061 fullphysics advanced but post-physicsmode-metadata repeated inspect of dynamicfunction failed; retainedactualsteps/mainAPIdelta and noqualificationrelabel. S2 modepatch now installs once and checks exact auditowneridentity;7localcasesPASS. Added finite commissioning-owner original API delta counters for subsequent evidence; prior worker counters retain disclosed gaps. Optional boundedfault adapter7localcasesPASS, originalrequest3 commissioning andTASK6/packet1 separated; nofaultenabledonSCI062. S2 fullSCI and reusability4run queue registered. QOFF.\n')
print('S2_REUSE4_REGISTERED')
