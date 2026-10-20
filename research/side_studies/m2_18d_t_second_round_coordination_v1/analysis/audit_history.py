from pathlib import Path
import json,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
before=json.loads((P/'audit/HISTORY_BEFORE.json').read_text());rows=[]
for name in ['m2_18d_baseline_qualification_v1','m2_18d_terminal_response_repair_v1','m2_18d_terminal_expanded_prefix_validation_v1','m2_18d_waypoint_smoothing_overnight_v1']:
 for fn in ['EVIDENCE_MANIFEST.json','EXECUTION_CODE_MANIFEST.json']:
  root=P.parent/name;f=root/fn;m=json.loads(f.read_text());missing=[];bad=[]
  for rel,rec in m['files'].items():
   path=Path(rel) if Path(rel).is_absolute() else root/rel
   h=rec['sha256'] if isinstance(rec,dict) else rec
   actual=before.get(str(path))
   if actual is None:missing.append(str(path))
   elif actual['sha256']!=h:bad.append(str(path))
  rows.append(dict(package=name,manifest=fn,manifest_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),files=len(m['files']),missing=missing,hash_mismatch=bad,status='PASS' if not(missing or bad) else 'FAIL'))
qual=[]
for name,conditions in [('m2_18d_terminal_response_repair_v1',['N2','U1']),('m2_18d_terminal_expanded_prefix_validation_v1',['V1','V2'])]:
 for c in conditions:
  root=P.parent/name;data=json.loads((root/(c+'_RESULTS.json')).read_text());rr=data['rows'];r=next(x for x in rr if x['arm']=='T')
  assert r['motion']['acceptance_pass'] and r['absolute_safety'] and r['task']=='PASS' and r['receipt']=='PASS'
  repeat=root/'audit'/(c+'_T_REPEAT.json')
  qual.append(dict(condition=c,motion=r['motion']['acceptance_pass'],J_F=r['J_F_N_s'],gain_percent=r['motion']['gain_percent'],task=r['task'],receipt=r['receipt'],safety=r['absolute_safety'],repeat_status=json.loads(repeat.read_text())['status'] if repeat.exists() else 'see original package repeat gate',source=str(root/(c+'_RESULTS.json'))))
out=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',source='SHA256 streamed from every original file at this session start; compare to original stored manifests without importing controller',manifests=rows,four_prefix_qualification=qual)
(P/'audit/HISTORICAL_MANIFESTS_VERIFIED.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out),flush=True)
