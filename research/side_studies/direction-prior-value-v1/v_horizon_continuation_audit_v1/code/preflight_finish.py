from freeze import *
import numpy as np
def main():
 out=STUDY/'output';zero=json.loads((out/'001_zero_regression_retry1.json').read_text());nonzero=json.loads((out/'003_model_probe_retry1.json').read_text());probe=json.loads((out/'MODEL_PROBE.json').read_text())
 assert zero['valid'] and zero['matched_eligible'];assert nonzero['valid'] and nonzero['matched_eligible']
 trace=STUDY/'source'/zero['trace'];old=ROOT/'stages/stage5_personalized_motion_learning/results/coordination_research_interface_v1/B_original/trace.npz'
 errors={}
 with np.load(trace) as new,np.load(old) as prior:
  for key in prior.files:
   assert key in new and new[key].shape==prior[key].shape,'ZERO_TRACE_SHAPE:'+key
   if prior[key].dtype.kind in 'fiu':
    assert np.array_equal(np.isnan(prior[key]),np.isnan(new[key]))
    mask=np.isfinite(prior[key]);errors[key]=float(np.max(np.abs(prior[key][mask]-new[key][mask]))) if np.any(mask) else 0.
   else:assert np.array_equal(prior[key],new[key]),'ZERO_TRACE_FIELD:'+key
 assert max(errors.values())<1e-10,'ZERO_PHYSICAL_CHANGED'
 assert all('prediction' in r for r in probe['rows']),'MODEL_PROBE_FAILED'
 initial_equal=all(np.array_equal(zero[key],nonzero[key]) for key in ('initial_estimated_state','initial_reference','model_beta','model_residual'))
 assert initial_equal,'MODEL_PROVISION_CHANGED_INITIAL_STATE'
 source=json.loads((STUDY/'SOURCE.json').read_text());changed=[p for p,h in source['original_files'].items() if sha(Path(p))!=h];assert not changed,'ORIGINAL_SOURCE_CHANGED'
 git_before=json.loads((STUDY/'GIT_BEFORE.json').read_text());assert git_before['index_sha256']==sha(ROOT/'.git/index'),'INDEX_CHANGED'
 audit=dict(status='PASS',zero_TRACE_errors=errors,zero_J_F=zero['J_F'],nonzero_J_F=nonzero['J_F'],physical_initial_and_execution_model_equal=initial_equal,known_model_parameter_only=True,source_changes=changed,known_parameters_sha256=sha(out/'KNOWN_MODEL_PARAMETERS.json'),forecast_model_calls=probe['model_calls'],quiet_baseline_wall_s=zero['host_s'],nonzero_wall_s=nonzero['host_s'],source_information_scope='KNOWN_MODEL research candidate prediction; unchanged frozen estimated B observer, actuator and safety model; no oracle physical initialization',historical_best_not_global_optimum=True)
 save(STUDY/'PREFLIGHT_GATE.json',audit)
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());cfg.update(information_condition='KNOWN_MODEL',information_scope=audit['source_information_scope'],preflight_gate_sha256=sha(STUDY/'PREFLIGHT_GATE.json'),forecast_tracking_model='causal current error, exp(-4 t/duration) internal hypothesis; future nodes labelled prediction-only; no physical receipt fabrication',horizon_rule='up to 3 native interior opportunities, terminate at phase endpoint if fewer remain; model continuation handles task HOLD/phase wait and remaining coordinated suffix',continuation_version='native-certified-committed-K3-suffix-v1',continuation_semantics='reapply remaining K3 table at each actual native B boundary; B revalidates graph against live observations and retains certified continuation on rejection; future suffix and native counts enter V input',frozen_unix=time.time())
 save(STUDY/'RUN_PLAN.json',cfg)
 print(json.dumps({k:audit[k] for k in ('status','zero_J_F','nonzero_J_F','quiet_baseline_wall_s','forecast_model_calls')}))
if __name__=='__main__':main()
