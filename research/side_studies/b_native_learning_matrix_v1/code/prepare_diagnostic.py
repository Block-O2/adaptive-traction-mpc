from task_bootstrap import *
from prepare import enqueue
import numpy as np

def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1'
 a=json.loads((STUDY/('ANALYSIS_'+version+'.json')).read_text());assert len(a['rows'])>=20,'COMPLETE_MATRIX_FIRST'
 # This is an exposed-state attribution study, never new held-out evidence.
 source=next(r for r in a['rows'] if r['method']=='M2' and r['valid'] and 'nominal_a' in r['group'])
 original=json.loads((STUDY/'output'/(source['id']+'_RESULT.json')).read_text());selections=json.loads((STUDY/'output'/(source['id']+'_SELECTIONS.json')).read_text())['rows']
 table=np.zeros((2,5,3))
 for row in selections:
  phase=row['context']['phase'];i=row['count_before'][phase]
  if i<5:table[('OUTBOUND','RETURN').index(phase),i]=np.asarray(row['applied_plan'])[('OUTBOUND','RETURN').index(phase),i]
 available={(r['context']['phase'],r['count_before'][r['context']['phase']]) for r in selections};targets=[list(x) for x in [('OUTBOUND',2),('RETURN',1)] if x in available];assert targets
 enqueue('060_'+version+'_committed_attribution',mode='diagnostic',group=version+'_committed_attribution',split='diagnostic',weights=original['inputs']['weights'],table=table.tolist(),targets=targets,candidates=6,budget_children=9*len(targets),seed=original['inputs']['seed'],replay_rows=selections,replay_source=source['id'],replay_trace=source['trace'],algorithm_sources=original['inputs']['algorithm_sources'],weights_sha256=original['inputs']['weights_sha256'])
 save(STUDY/('DIAGNOSTIC_CONTRACT_'+version+'.json'),dict(frozen_unix=time.time(),source=source['id'],targets=targets,maximum_new_attempts=1+9*len(targets),same_native_state_required=True,exact_executed_replay_required=True,ordinary_six='exact preserved M2 ordinary pool, not regenerated',G='three frozen heads added offline only',purpose='G coverage, Q committed-suffix regret, committed versus preserved rolling continuation',never_training=True,no_new_physical_authority=True))
 print('REPRESENTATIVE_DIAGNOSTIC_QUEUED',1+9*len(targets))
if __name__=='__main__':main()
