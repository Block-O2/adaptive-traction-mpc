from study_common import *
from task_bootstrap import save as write,ROOT
from prepare import enqueue
def main():
 a=read('002_original_B_retry1_RESULT.json');b=read('003_zero_interface_retry1_RESULT.json');assert a['status']==b['status']=='COMPLETE'
 aa=a['metric'];bb=b['metric'];errors={}
 assert aa['valid'] and bb['valid'] and aa['matched_eligible'] and bb['matched_eligible']
 for key in ('J_F','moment_integral','duration_s'):assert abs(aa[key]-bb[key])<1e-10,key
 with np.load(R/aa['trace']) as x,np.load(R/bb['trace']) as y:
  for key in x.files:
   assert key in y and x[key].shape==y[key].shape,key
   if x[key].dtype.kind in 'fiu':
    assert np.array_equal(np.isnan(x[key]),np.isnan(y[key]));finite=np.isfinite(x[key]);errors[key]=float(np.max(np.abs(x[key][finite]-y[key][finite]))) if finite.any() else 0.
   else:assert np.array_equal(x[key],y[key]);errors[key]=0.
 assert max(errors.values())<1e-10,'ZERO_BASELINE_REGRESSION'
 old=ROOT/'stages/stage5_personalized_motion_learning/results/coordination_research_interface_v1/B_original/trace.npz'
 historical={}
 if old.exists():
  with np.load(R/aa['trace']) as x,np.load(old) as y:
   for key in y.files:
    assert key in x and x[key].shape==y[key].shape,key
    if y[key].dtype.kind in 'fiu':
     finite=np.isfinite(y[key]);historical[key]=float(np.max(np.abs(x[key][finite]-y[key][finite]))) if finite.any() else 0.
    else:assert np.array_equal(x[key],y[key]);historical[key]=0.
  assert max(historical.values())<1e-10,'FROZEN_B_HISTORY_CHANGED'
 write(STUDY/'B_ZERO_GATE.json',dict(status='PASS',zero_errors=errors,historical_B_errors=historical,J_F=aa['J_F'],moment_integral=aa['moment_integral'],phase_durations=aa['phase_durations'],baseline_wall_s=a['wall_seconds'],zero_wall_s=b['wall_seconds'],P_calls=[a['P_full_performance_calls'],b['P_full_performance_calls']],source='same original B runtime plus approved native residual v2; no P planning modules'))
 write(STUDY/'PROTOCOL.json',dict(version=1,frozen_unix=time.time(),Q='direct current-state/current-candidate expected remaining current-repetition J_F N s; no prefix, no next repetition, no P base',continuation='committed masked K3 table on actual native requests; unchanged certification/rejection/fallback; B when suffix ends',input_dim=120,inputs='55D causal commissioned B features, 3 residual history, 30 masked U, 30 masked carry, 2 issued counts',G='up to three distinct proposal heads; only executed valid complete outcomes; no opposite-action averaging',S='existing B single-segment _evaluate total_cost through original cloned adaptive decide; dimensionless task-goal/change/completion terms, not force prediction or whole-repetition score',safety='native scheduler/mechanics/ROM/continuous clearance/tracking-offset checks unchanged, terminal/HOLD remains B',ordinary_candidates=['B','valid carry','historical qualified design reference','positive .25','negative -.25','reversal [.35,-.25,.15]'],candidate_budget=6,training='linear plus 2x128 Q MLP; G 2x128 three heads; parent groups held together; model selection dev only; max two rounds',evaluation='minimum four paired full runs all five defined methods; nominal/legally executed prefixes, identical seeds and info',latency='native 40ms bridge; independently scored 55ms activation requirement, generic 100ms expiration; cannot extend bridge or rewrite executed actions',promotion='quality benefit if all complete comparable pairs improve and average paired J_F >=0.5%, no task or safety loss; timing reported separately; exposed Human only',heldout_groups=['final_nominal_a','final_nominal_b','final_deviation_positive','final_deviation_negative'],test_rules='final repetitions never training; common initial-state overlap disclosed; shared prefixes held paired; no claim new Human/noise robustness'))
 write(STUDY/'CHECKPOINT.json',dict(phase='B_ZERO_QUALIFIED',next='single-state CPU fork smoke then three grouped parents with bounded candidates',start_unix=json.loads((STUDY/'RUN_PLAN.json').read_text())['start_unix']))
 enqueue('010_branch_smoke',mode='branches',group='smoke',split='smoke',targets=[['OUTBOUND',2]],candidates=2,budget_children=2)
 print(json.dumps(dict(status='PASS',J_F=aa['J_F'],wall_s=a['wall_seconds'])))
if __name__=='__main__':main()
