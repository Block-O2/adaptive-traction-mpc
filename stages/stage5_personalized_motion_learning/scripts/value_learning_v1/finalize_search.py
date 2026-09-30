"""Freeze finite-budget matched and native references with explicit objective scope."""
import csv,json
from collections import Counter
from datetime import datetime,timezone
from research_campaign import D,RAW,RUNS,C,save,summarize_reference
from native_objective_extension import native_sources,summarize

def main():
 summarize_reference();sources=native_sources();summarize(sources)
 matched=json.loads((D/'BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 native=json.loads((D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 attempts=[]
 for path in sorted((RAW/'search_proposals').glob('*.json')):
  entry=json.loads(path.read_text());rp=RUNS/entry['run_id']/'rollout_result.json'
  if not rp.exists():continue
  result=json.loads(rp.read_text())
  if result['status']=='RUNNING':continue
  attempts.append({**entry,'status':result['status'],'J_F_n_s':result.get('J_F_task_n_s')})
 for row in matched['rows']:
  row['reference_scope']='conditional matched scheduling, not unrestricted primary objective'
  row['level_evaluations']={str(l):sum(a['condition']==row['condition'] and a['level']==l for a in attempts) for l in (1,2,3)}
  row['restart_generation_evaluations']={f'L{l}_R{r}_G{g}':sum(a['condition']==row['condition'] and a['level']==l and a['restart']==r and a['generation']==g for a in attempts)
   for l in (1,2,3) for r in (0,1) for g in (0,1,2)}
  row['incomplete_levels_cannot_establish_plateau']=[l for l in (1,2,3) if row['level_evaluations'][str(l)]<2*3*8]
 native['status']='COMPLETE_FINITE_BUDGET_SEARCH';native['not_global_optimum']=True
 for row in native['rows']:
  row['reference_scope']='absolute measured cuff-force integral; native timing may change'
  row['timing_isolated_claim']=False
 matched.update(status='COMPLETE_FINITE_BUDGET_SEARCH',not_global_optimum=True,
  primary_objective_rows=native['rows'],
  scope='rows are conditional matched-duration references; primary_objective_rows are native-scheduler absolute references',
  current_learning_scope='matched-only fitted models and pilot; native data excluded from fitting')
 save(D/'BEST_KNOWN_REFERENCE_TABLE.json',matched);save(D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json',native)
 primary=[]
 for m,n in zip(matched['rows'],native['rows']):
  assert m['condition']==n['condition']
  primary.append({**n,'matched_conditional_best_J_F_n_s':m['best_known_J_F_n_s'],
   'absolute_best_reference_scope':'NATIVE_SCHEDULER' if n['best_known_J_F_n_s']<=m['best_known_J_F_n_s'] else 'MATCHED_SCHEDULER',
   'absolute_best_known_J_F_n_s':min(n['best_known_J_F_n_s'],m['best_known_J_F_n_s']),
   'matched_pilot_does_not_automatically_capture_absolute_benefit':True})
 save(D/'ABSOLUTE_PRIMARY_REFERENCE_TABLE.json',{'status':'COMPLETE','rows':primary,'no_global_optimality':True})
 curve=[]
 for filename,scope in [('REFERENCE_SEARCH_CONVERGENCE.json','MATCHED_CONDITIONAL'),('NATIVE_REFERENCE_SEARCH_CONVERGENCE.json','NATIVE_PRIMARY')]:
  for row in json.loads((D/filename).read_text()):curve.append({**row,'scope':scope})
 save(D/'ALL_REFERENCE_SEARCH_CONVERGENCE.json',curve)
 keys=sorted(set(k for row in curve for k in row))
 with (D/'ALL_REFERENCE_SEARCH_CONVERGENCE.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(curve)
 text=['# Best-known reference search','',
  'Primary objective is completed-task measured cuff-force integral with hard safety validity. Native and matched scheduling have different achievable costs. The matched learner study is conditional; its reference is never an unrestricted performance limit.','',
  '|Condition|Matched previous|Matched best|Native previous|Native best|Matched evals|Native evals|',
  '|---|---:|---:|---:|---:|---:|---:|']
 for m,n in zip(matched['rows'],native['rows']):text.append(f'|{m["condition"]}|{m["previous_best_J_F_n_s"]:.6f}|{m["best_known_J_F_n_s"]:.6f}|{n["previous_best_J_F_n_s"]:.6f}|{n["best_known_J_F_n_s"]:.6f}|{m["evaluations"]}|{n["evaluations"]}|')
 text+=['','Units N·s. Level-wise envelopes retain earlier levels and prior references; an unchanged envelope with sparse/missing evaluations is not a plateau. Restart results, feasibility, completed generation counts, phase timing residuals and descriptors are in the JSON tables.','',
  'Directed CEM evaluates real frozen Scientific Simulation. Every rejection remains recorded. Population/restart and finite wall-time budgets limit coverage; no lower bound or global-optimality evidence is claimed. Level 4 was not exercised in this bounded campaign.','',
  'New winning paths are independently re-executed from their exact frozen discovery starting state. Deterministic agreement does not establish Human-subject generalization. Native cost changes are not called timing-isolated coordination gains.']
 (D/'BEST_KNOWN_REFERENCE_SEARCH.md').write_text('\n'.join(text)+'\n')
 save(D/'REFERENCE_SEARCH_FINALIZATION.json',{'status':'COMPLETE','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'matched_completed_evaluations':sum(r['evaluations'] for r in matched['rows']),
  'native_completed_evaluations':native['evaluations'],'all_proposals_real_scientific_evaluations':True,
  'finite_budget_not_optimality':True,'no_level4_claim':True})
if __name__=='__main__':main()
