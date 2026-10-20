from prepare_tasks import *
def main():
 assert json.loads((STUDY/'versions/E1_EQUIVALENCE_GATE.json').read_text())['status']=='PASS'
 files=['optimized_method.py','shared_nominal.py','q_first_method.py','native_method.py','native_core.py','native_inference.py','interfaces.py','worker.py']
 source={str(STUDY/'code'/f):sha(STUDY/'code'/f) for f in files}
 save(STUDY/'versions/E2_CONTRACT.json',dict(optimization='E1 plus Q-first full native certification',scientific_shadow='all candidates validated after fast-prefix selection to prove acceptance and baseline subset-Q ranking',near_tie='conservative floating-point dot bound -> full original validation and feasible-subset Q ranking',fallback='original carry when no accepted candidate',scientific_version='EXACT_EQUIVALENT_PENDING_GATE',algorithm_sources=source))
 for id,method,prefix,seed in [('020_E2_science_B','M0',{},2026100621),('021_E2_science_M2','M2',{},2026100621),('022_E2_science_deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  enqueue(id,method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version='E2',execution_mode='SCIENTIFIC_SIMULATION',algorithm_sources=source)
 print('E2_EQUIVALENCE_SHADOW_REGRESSIONS_QUEUED')
if __name__=='__main__':main()
