from explore_common import *
from campaign_explore import run,attempts
def main():
 assert (S/'CAMPAIGN_STOP.json').exists(),'NO_PARALLEL_PHYSICS'
 p=load(S/'BASELINE_REPEAT_PROTOCOL.json');assert sha(Path(__file__))==p['script_sha256'];assert len([r for r in attempts() if r['event']=='START'])<=22
 if (S/'BLOCKER.json').exists():save(S/'BASELINE_REPEAT_RESULTS.json',dict(status='NOT_RUN_NATIVE_GATE_STOP',rows=[]));return
 template=load(S/'queue/001_search_B.json');rows=[]
 try:
  for n in [1,2]:
   cfg=dict(template);cfg.update(id=f'diagnostic_B_repeat_{n}',split='attribution_diagnostic',pair_id='discovery_seed_B_repeats',seed=p['seed']);rows.append(run(cfg))
 finally:
  base=load(S/'reports/001_search_B_MEASURED.json');allrows=[base]+rows
  save(S/'BASELINE_REPEAT_RESULTS.json',dict(status='COMPLETE_EXPLORATORY_DIAGNOSTIC' if len(rows)==2 else 'PARTIAL_STOPPED',rows=allrows,J_F_range_N_s=max(r['J_F_N_s'] for r in allrows)-min(r['J_F_N_s'] for r in allrows),phase_J_F_range_N_s={ph:max(r['phase_cost']['phases'][ph]['J_F_N_s'] for r in allrows)-min(r['phase_cost']['phases'][ph]['J_F_N_s'] for r in allrows) for ph in ['OUTBOUND','HOLD','RETURN']},no_candidate_reselection=True,independent_candidate_validation=False))
  save(S/'DIAGNOSTIC_STOP.json',dict(unix=time.time(),attempts=attempts(),new_runs=len(rows),worker_parent_exiting=True))
if __name__=='__main__':main()
