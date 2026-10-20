"""Bind the preregistered diversity rule to actual slot/shape regions."""
from pathlib import Path
import json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1')
def put(name,x):(S/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def region(c):
 if 'table' in c:return ('K3',tuple(ph for i,ph in enumerate(['OUTBOUND','RETURN']) if any(any(v) for v in c['table'][i])))
 return tuple((ph,tuple(i for i,s in enumerate(specs) if s is not None),tuple(sorted({(s['shape'],tuple(s['knots']),tuple(s['support'])) for s in specs if s is not None}))) for ph,specs in sorted(c['phases'].items()))
def main():
 events=[json.loads(r) for r in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
 assert not any(r['event']=='START' and r['id'].startswith(('H1_','H2_')) for r in events),'NO_HELDOUT_INFLUENCE'
 assert (S/'DISCOVERY_STOP.json').exists(),'DISCOVERY_NOT_FINISHED'
 old=json.loads((S/'FROZEN_SELECTION.json').read_text());catalog={r['id']:r for r in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
 rows=[json.loads(r) for r in (S/'RESULTS.jsonl').read_text().splitlines()];valid=[r for r in rows if r['id'].startswith('discovery_') and r['comparison']['eligible'] and r['candidate_id']!='Frozen_M2']
 ordered=sorted(valid,key=lambda r:(-r['comparison']['gain_percent'],r['candidate_id']));chosen=[]
 if ordered:
  chosen=[ordered[0]]
  smooth=min(valid,key=lambda r:(max(max(v) for v in r['comparison']['burden_ratios'].values()),-r['comparison']['gain_percent'],r['candidate_id']))
  if smooth not in chosen:chosen.append(smooth)
  for r in ordered:
   if r not in chosen and region(catalog[r['candidate_id']])!=region(catalog[chosen[0]['candidate_id']]):chosen.append(r);break
 new={**old,'unix':time.time(),'candidates':[catalog[r['candidate_id']] for r in chosen[:3]],'discovery_rows':chosen[:3],'eligible_count':len(valid),'diversity_region_definition':'phase + issued-slot mask + PWL shape/knots/support, ignores missing phase shorthand in C4 parameters','no_holdout_used':True,'candidate_parameters_unchanged':True}
 put('FROZEN_SELECTION_INITIAL_IMPLEMENTATION.json',old)
 put('SELECTION_BOOKKEEPING_REPAIR.json',dict(unix=time.time(),reason='C4 parameters record region_source/factor and have no phase shorthand; initial selector compared missing phase=None instead of intended slot/shape region',protocol_rule='max3 representatives: minimum J_F, minimum raw burden, distinct parameter region; all already eligible discovery parameters frozen',initial_ids=[r['id'] for r in old['candidates']],final_ids=[r['id'] for r in new['candidates']],parameters_revised=False,heldout_used=False,helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
 put('FROZEN_SELECTION.json',new)
 print(json.dumps(dict(frozen_ids=[r['id'] for r in new['candidates']],eligible=len(valid),no_heldout_used=True)),flush=True)
if __name__=='__main__':main()
