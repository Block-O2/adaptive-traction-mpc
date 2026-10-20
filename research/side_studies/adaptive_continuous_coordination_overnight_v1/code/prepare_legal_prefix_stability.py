"""CASE4 frozen-Q lawful-deviation stability; not host-qualified Phase C."""
from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 ended={json.loads(line)['id'] for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(line)['event']=='END'}
 assert all(any(id.startswith(str(k)+'_E6_LEAN') for id in ended) for k in range(240,248)),'QUIET_HOST_SERIES_MUST_FINISH_FIRST'
 starts=sum(json.loads(line)['event']=='START' for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines());assert starts+16<=160 and time.time()+2400<START+8.25*3600,'SAFE_CASE4_BUDGET'
 prefixes=[{'OUTBOUND':[[.30,-.10,.05]]},{'OUTBOUND':[[-.15,.25,-.20]]},{'OUTBOUND':[[.10,.05,-.30]],'RETURN':[[.20,-.10,.15]]},{'OUTBOUND':[[-.25,-.10,.20]],'RETURN':[[-.10,.15,-.25]]},{'OUTBOUND':[[.05,.30,-.20],[-.20,.10,.25]]},{'OUTBOUND':[[.25,.10,-.15],[-.10,-.20,.30]],'RETURN':[[.10,-.15,.05]]},{'OUTBOUND':[[-.20,.20,.10],[.15,-.25,.05]],'RETURN':[[-.15,.05,.20],[.20,.10,-.25]]},{'OUTBOUND':[[.10,-.10,.25],[.25,.15,-.20],[-.15,.20,.10]],'RETURN':[[.05,.25,-.10]]}]
 sources=frozen_sources()
 for f in ('lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 rows=[]
 for j,prefix in enumerate(prefixes):
  for method in (('M0','M2') if j%2==0 else ('M2','M0')):
   index=260+2*j+(0 if method==('M0' if j%2==0 else 'M2') else 1);id=f'{index:03d}_LEGAL_STABILITY_P{j+1}_'+('B' if method=='M0' else 'frozenQ');seed=2026100811+j
   rows.append(dict(id=id,pair=j+1,method=method,seed=seed,prefix=prefix))
 # Protocol saved before any dispatch; interventions are specified without
 # examining outcomes, no search or training chooses their amplitudes.
 save(STUDY/'versions/LEGAL_PREFIX_STABILITY_PROTOCOL.json',dict(classification='CASE4_EXPOSED_NOMINAL_FROZEN_Q_SCI_STABILITY_NOT_HOST_QUALIFIED_PHASE_C',rows=rows,additional_physical_attempts=16,attempts_before_dispatch=starts,purpose='Expand lawful causal-state coverage after complete-suffix labels were insufficient and true continuous SCI hit unchanged R2 timing failure at Rep4. Distinct prescribed prefix interventions and distinct candidate RNG seeds; no Human truth change or new Human claim.',prefix_amplitudes='Existing native K3 graph_action(a*0.2,current_start_m), all declared a in [-1,1]; unchanged native feasibility checks may reject any proposal.',scientific_version='frozen-B-native-Q-v1',timing_version='E5_LEAN_v1',Q_updates=0,new_control_or_public_B_repairs=0,full_native_gate='E6_LEAN PASS for original B/M2/legal deviation',host_qualification=False,algorithm_sources=sources))
 for r in rows:
  enqueue(r['id'],method=r['method'],original=False,prefix=r['prefix'],seed=r['seed'],timing_version='E5_LEAN_v1',execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=r['method']=='M2',research_profile=False,algorithm_sources=sources,stability_pair=r['pair'],stability_classification='CASE4_EXPOSED_NOMINAL_FROZEN_Q_SCI_ONLY')
 print(json.dumps(dict(registered_attempts=16,unique_prefix_pairs=8,physics_after_if_all_dispatch=starts+16,classification='CASE4_SCI_STABILITY_ONLY_NO_HOST_QUALIFICATION')))
if __name__=='__main__':main()
