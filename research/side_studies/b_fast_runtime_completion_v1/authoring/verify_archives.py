"""Stream this package's compressed outputs once; reconcile real receipts."""
from pathlib import Path
import sys,gzip,json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
ledger=json.loads((S/'TASK_LEDGER.json').read_text());rows=[];verified=[]
for p in sorted((S/'source/results').rglob('*.gz')):
 try:
  n=0
  with gzip.open(p,'rb') as f:
   for b in iter(lambda:f.read(2**20),b''):n+=len(b)
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
  verified.append(dict(path=str(p.relative_to(S)),compressed_bytes=p.stat().st_size,uncompressed_bytes=n,CRC_verified=True,compressed_sha256=h.hexdigest()))
 except BaseException as e:
  raise RuntimeError('INVALID_ARCHIVE '+str(p)) from e
for ident,v in ledger.items():
 p=S/'source/results'/ident/'runtime_artifacts.json.gz';old=v.get('compute',{}).get('native_physics_steps')
 if p.exists():
  total=sum(x.get('native_steps',0) for x in array_items(p,'command_receipts'));authority='every actual command receipt, including final catch-up'
 elif ident.startswith(('024_','047_','058_')):
  assert v.get('error') in ("'HOST_REALTIME' is not a valid ExecutionMode","'REALTIME_EXECUTION' is not a valid ExecutionMode",'SERIALIZER_SOURCE_CHANGED')
  total=0;authority='Startup rejection before physical runtime construction; original missing metric retained'
 else:total=old;authority='recorded partial or local native-step metric; no complete receipt artifact'
 rows.append(dict(id=ident,original_ledger_steps=old,reconciled_actual_steps=total,authority=authority,difference=None if old is None or total is None else total-old))
assert all(isinstance(x['reconciled_actual_steps'],int) for x in rows)
out=dict(unix=time.time(),status='PASS',physics_dispatched=0,model_API_calls=0,verified_archives=verified,receipt_reconciliation=rows,total_recorded_native_steps=sum(x['reconciled_actual_steps'] for x in rows),simulation_seconds=sum(x['reconciled_actual_steps'] for x in rows)*.00025,note='Local paired plant tests count both plants. Early partial metrics remain less informative than full ownership receipts; this is a reconciled measurement, not a task qualification.')
(S/'reports/FINAL_ARCHIVE_AND_RECEIPT_VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n')
print('ARCHIVES_AND_RECEIPTS_PASS',len(verified),out['total_recorded_native_steps'],flush=True)
