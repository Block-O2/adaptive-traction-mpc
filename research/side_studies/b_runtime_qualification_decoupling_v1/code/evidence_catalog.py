"""Compact provenance inventory for report authoring; no control mutation."""
from task_bootstrap import *
def main():
 rows=[];versions=[];offline=[]
 for folder in ('versions','reports'):
  for p in sorted((STUDY/folder).glob('*.json')):
   if 'HISTORY_' in p.name or p.name=='EVIDENCE_CATALOG.json':continue
   x=json.loads(p.read_text());row=dict(relative_path=str(p.relative_to(STUDY)),sha256=sha(p),bytes=p.stat().st_size)
   if isinstance(x,dict):
    row.update({k:x[k] for k in ('status','version','comparisons','attempts','physics_attempts_added','baseline_C2_mean_ms','compiled_mean_ms','reduction_percent') if k in x})
    if 'GATE' in p.name:row['cases']=[dict(baseline=r.get('baseline'),optimized=r.get('optimized'),status=r.get('status'),issues=r.get('issues'),native_step_counts=r.get('native_step_counts'),full_native_step_signature_exact=r.get('full_native_step_signature_exact')) for r in x.get('rows',[])];versions.append(row)
    if 'OFFLINE' in p.name or p.name.startswith('WIDE'):offline.append(row)
   rows.append(row)
 events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if line.strip()];starts=[e for e in events if e['event']=='START'];ends=[e for e in events if e['event']=='END'];open_ids=set(e['id'] for e in starts)-set(e['id'] for e in ends);result_ids={json.loads(p.read_text())['id'] for p in (STUDY/'output').glob('*_RESULT.json')}
 out=dict(status='READ_ONLY_CATALOG',generated_unix=time.time(),entries=rows,version_gates=versions,offline_studies=offline,physical_attempts=len(starts),ended=len(ends),open_ids=sorted(open_ids),ended_missing_results=sorted(set(e['id'] for e in ends)-result_ids),Q_weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'))
 save(STUDY/'reports/EVIDENCE_CATALOG.json',out);print(json.dumps({k:out[k] for k in ('version_gates','offline_studies','physical_attempts','ended','open_ids','ended_missing_results')}))
if __name__=='__main__':main()
