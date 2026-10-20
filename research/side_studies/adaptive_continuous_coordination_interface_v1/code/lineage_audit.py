from pathlib import Path
import json,numpy as np
S=Path(__file__).resolve().parent.parent
def numeric(c):
 out={ph:[None]*5 for ph in ['OUTBOUND','RETURN']}
 if 'table' in c:
  for j,ph in enumerate(out):
   for i,a in enumerate(c['table'][j]):
    if any(a):out[ph][i]=dict(knots=[.1,.4,.7],support=[0,1],values=(np.asarray(a)*.2).tolist())
 else:
  for ph,ss in c.get('phases',{}).items():
   for i,sp in enumerate(ss):
    if sp is not None and any(sp['values']):out[ph][i]={k:sp[k] for k in ['knots','support','values']}
 return out
def build():
 cc={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']};ev=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()];out=[]
 for r in ev:
  c=cc.get(r['candidate_id'])
  if c is None:continue
  pp=c.get('parameters',{});source=cc.get(pp.get('direct_parent')) or cc.get(pp.get('source'));a=numeric(source or {});b=numeric(c);changes=[]
  for ph in a:
   for i,(x,y) in enumerate(zip(a[ph],b[ph])):
    if x!=y:changes.append(dict(phase=ph,slot=i,before=x,after=y))
  isolate=pp.get('changes',{}).get('operation')=='phase_isolation';kept=pp.get('changes',{}).get('kept');pure_isolate=bool(isolate and all(x['phase']!=kept for x in changes))
  out.append(dict(id=r['id'],source=None if source is None else source['id'],registered_changes=changes,declared_operation=pp.get('changes'),pure_phase_isolation=pure_isolate if isolate else None,single_registered_slot_change=len(changes)==1,actual_native_changes_reference=r['runtime_lineage_path'],interpretation='registered parameter contrast; subsequent native timing/sampling may also change. Parameter equality is not a global action-equivalence claim.'))
 p=S/'REGISTERED_CHANGE_AUDIT.json';p.write_text(json.dumps(dict(rows=out,phase_isolation_mixed_interventions=[r['id'] for r in out if r['pure_phase_isolation'] is False],no_physics_or_acceptance_changed=True),indent=2,ensure_ascii=False)+'\n');return out
if __name__=='__main__':print(json.dumps(dict(rows=len(build()))))
