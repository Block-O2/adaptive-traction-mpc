from prepare_tasks import *
import numpy as np
def main():
 rows=[]
 for id in ('003_T0_science_M2','011_E1_science_M2','012_E1_science_deviation'):
  s=json.loads((STUDY/'output'/(id+'_SELECTIONS.json')).read_text())['rows'];c=STUDY/'output'/(id+'_CACHE_EVIDENCE.json')
  rows.append(dict(id=id,coordinator_ms_quantiles=np.quantile([r['end_to_end_s']*1000 for r in s],[.5,.9,.95,1]).tolist(),cache=[] if not c.exists() else [(x['hits'],x['misses']) for x in json.loads(c.read_text())['rows']]))
 out=dict(rows=rows,B2=dict(status='RETAINED_MANDATORY_NATIVE_NOMINAL_SCORING',reason='Original B uses S to choose its nominal waypoint inside original decide; M2 outer residual Q does not replace that native ranking. Residual extra total_cost arithmetic is tiny and inseparable from immutable candidate record, no certificate removed.'),B3=dict(status='SHARED_NOMINAL_REUSE_E1',candidate_specific_certificates_retained=True),B5=dict(status='BUFFERED_PROFILING_AND_POST_RUN_PERSISTENCE',no_profile_disk_io_in_decision=True))
 save(STUDY/'reports/PHASE_B_CURRENT.json',out);print(json.dumps(out))
 assert json.loads((STUDY/'versions/E1_EQUIVALENCE_GATE.json').read_text())['status']=='PASS'
 enqueue('013_E1_wall_M2',timing_version='E1',execution_mode='REALTIME_CHARACTERIZATION',delay_replay=True)
if __name__=='__main__':main()
