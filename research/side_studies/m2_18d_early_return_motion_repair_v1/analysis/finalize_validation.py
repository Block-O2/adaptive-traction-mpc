from pathlib import Path
import json,time,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
rs=read('EXPERIMENT_RESULTS.json')['rows'];sel=read('REPAIR_FROZEN_SELECTION.json');primary=sel['primary'];rep=[];held=[];gate=None
if primary:
 freeze=read('VALIDATION_CODE_AND_PARAMETER_FREEZE.json')
 for n,h in freeze['frozen_files'].items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 assert hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest()==freeze['execution_manifest_sha256']
 rep=[r for r in rs if r['id'].startswith('repeat_') and r['candidate'].get('early')]
 held=[r for r in rs if r['id'].startswith('W2_') and r['candidate'].get('early')]
 path=P/'audit'/('repeat_'+primary+'_repeat_REPEAT_GATE.json');gate=read(str(path.relative_to(P))) if path.exists() else None
repeat_pass=bool(len(rep)==2 and all(r['all_original_qualifications'] and r.get('eligible_primary') for r in rep) and gate and gate['status']=='PASS')
held_pass=bool(len(held)==1 and held[0]['all_original_qualifications'] and held[0].get('eligible_primary'))
status='FINITE_CROSS_PREFIX_QUALIFIED' if repeat_pass and held_pass else 'DEVELOPMENT_QUALIFIED_VALIDATION_FAILED_OR_INCOMPLETE' if primary else 'NO_FULLY_QUALIFIED_REPAIR'
out=dict(status=status,unix=time.time(),primary=primary,selection=sel,development_qualified=primary is not None,deterministic_repeat_executed=bool(rep),deterministic_repeat_pass=repeat_pass,deterministic_repeat_gate=gate,independent_unused_legal_prefix_executed=bool(held),independent_unused_legal_prefix_pass=held_pass,validation_runs=[dict(id=r['id'],all_original_qualifications=r['all_original_qualifications'],failed=r['motion']['failed_requirements'],gain_vs_own_B_percent=r['motion']['gain_percent'],J_F_N_s=r['J_F_N_s'],D_force_saving_retention_fraction=r.get('D_force_saving_retention_fraction'),intervention_executed=r['intervention_executed']) for r in rep+held],frozen_T_failures_retained=[dict(id=r['id'],failed=r['motion']['failed_requirements']) for r in rs if r['candidate']['id']=='T' and not r['all_original_qualifications']],formal_B_or_T_D_identity_replaced=False,scope='same fixed Human/robot model and exact registered W1/W2 legal graph prefixes, original full task gates in SCIENTIFIC_SIMULATION; no arbitrary-state, cross-patient, clinical, hardware or host realtime qualification',validation_results_not_used_for_primary_reselection=True,new_physics_required_for_numerical_recheck=False)
if not held:out['scope']='same fixed Human/robot model, W1 development only; W2 was registered but never physically executed; no independent-state validation, arbitrary-state, cross-patient, clinical, hardware or host realtime qualification'
put('VALIDATION_RESULTS.json',out);print(json.dumps(out),flush=True)
