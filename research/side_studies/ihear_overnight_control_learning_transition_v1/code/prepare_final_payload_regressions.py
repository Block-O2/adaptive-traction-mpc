from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ['capture_states.py','certified_snapshot_v2.py','certified_apply.py']:sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 version='E3T_C2A';save(STUDY/'versions'/(version+'_CONTRACT.json'),dict(version=version,parent='E3T_C2',public_engineering_version_unchanged='C2_THREAD',optimization='Full native decision certificate for actual submitted late carry/prefix/terminal when Q-first did not evaluate that exact input; eliminates duplicate worker calculation without changing submitted action',classification='EXACT_EQUIVALENT_PENDING_GATE',algorithm_sources=sources,current_model_activation_revalidation_retained=True,one_boundary_cache_no_state_or_owner_reuse=True))
 for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  enqueue(f'{80+offset:03d}_{version}_science_{label}',method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version=version,public_version='C2_THREAD',execution_mode='SCIENTIFIC_SIMULATION',capture_states=method=='M2',certificate_version='v2',certify_final_payload=True,algorithm_sources=sources)
 for id,pub in [('090_C2_characterization_B','C2_THREAD'),('091_C1_characterization_B','C1_THREAD'),('092_T0_characterization_B',None)]:
  enqueue(id,method='M0',original=True,timing_version=version,public_version=pub,execution_mode='REALTIME_CHARACTERIZATION',algorithm_sources=sources)
 print('ACTUAL_PAYLOAD_REUSE_EQUIVALENCE_GATE_QUEUED')
if __name__=='__main__':main()
