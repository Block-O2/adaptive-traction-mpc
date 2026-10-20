from prepare_tasks import *
def main():
 files=['optimized_method.py','shared_nominal.py','q_first_method.py','native_method.py','native_core.py','native_inference.py','interfaces.py','worker.py']
 source={str(STUDY/'code'/f):sha(STUDY/'code'/f) for f in files}
 save(STUDY/'versions/E2r1_CONTRACT.json',dict(parent='E2',repair='Explicit NativeInterface.choose call for lawful prefix; fixes Python unbound method super type mismatch only',failed_attempt='022_E2_science_deviation',same_Q_candidates_certificates=True,algorithm_sources=source))
 for id,method,prefix,seed in [('025_E2r1_science_B','M0',{},2026100621),('026_E2r1_science_M2','M2',{},2026100621),('027_E2r1_science_deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  enqueue(id,method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version='E2r1',execution_mode='SCIENTIFIC_SIMULATION',algorithm_sources=source)
 print('E2r1_MINIMAL_ROUTING_REPAIR_REGRESSIONS_QUEUED')
if __name__=='__main__':main()
