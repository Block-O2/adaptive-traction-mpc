from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 sources=frozen_sources()
 for f in ('lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 for offset,label,method,prefix,seed in [(0,'B','M0',{},2026100621),(1,'M2','M2',{},2026100621),(2,'deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623)]:
  enqueue(f'{230+offset:03d}_E6_LEAN_science_{label}',method=method,original=method=='M0',prefix=prefix,seed=seed,timing_version='E5_LEAN_v1',execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=method=='M2',research_profile=False,algorithm_sources=sources)
 save(STUDY/'versions/E6_LEAN_CONTRACT.json',dict(status='EXACT_EQUIVALENT_PENDING_GATE',changes='Only remove nested research event wrappers and audit lock counters from command path. Original native timing requests/actual receipts/full trace/API counters and P firewall retained.',same_B_scheduling_and_physics=True,public_B_engineering_repairs_still_two=True,gate=['ZERO/B','frozen M2','legal deviation','full native physical and q/dq/ddq references'],algorithm_sources=sources))
 print('E6_LEAN_THREE_SCI_GATES_QUEUED')
if __name__=='__main__':main()
