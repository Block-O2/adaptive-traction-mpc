"""Preregister identities and comparisons before any physical START."""
from pathlib import Path
import json,time,hashlib,copy,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(__file__).resolve().parent
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert (P/'BOOTSTRAP_DONE.json').exists()
assert not (P/'VIRTUAL_PATIENT_COHORT.json').exists(),'Preregistration is immutable'
assert not (P/'ATTEMPTS.jsonl').exists()
base=json.loads((P/'source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text())
oldplan=json.loads((P/'provenance/HISTORICAL__D01R_PLAN.json').read_text())
arms=[copy.deepcopy(a) for a in oldplan['arms'] if a['id'] in ['B','H150']]
design=[
 ('P00','reference',1,1,1,1,{}),
 ('P01','mass_low',1,.8,1,1,{}),
 ('P02','mass_high',1,1.2,1,1,{}),
 ('P03','length_short',.95,1,1,1,{}),
 ('P04','length_long',1.05,1,1,1,{}),
 ('P05','stiffness_low',1,1,.7,1,{}),
 ('P06','stiffness_high',1,1,1.3,1,{}),
 ('P07','damping_low',1,1,1,.7,{}),
 ('P08','damping_high',1,1,1,1.3,{}),
 ('P09','compound_short_light',.95,.8,1.3,.7,dict(thigh_com_fraction=.40,shank_com_fraction=.40,thigh_inertia_radius_fraction=.28,shank_inertia_radius_fraction=.28)),
 ('P10','compound_long_heavy',1.05,1.2,.7,1.3,dict(thigh_com_fraction=.46,shank_com_fraction=.46,thigh_inertia_radius_fraction=.32,shank_inertia_radius_fraction=.32)),
 ('P11','compound_asymmetric',1,1,1.3,1.3,dict(thigh_length_scale=1.03,shank_length_scale=.97,thigh_mass_scale=1.1,shank_mass_scale=.9,thigh_com_fraction=.45,shank_com_fraction=.41,thigh_inertia_radius_fraction=.31,shank_inertia_radius_fraction=.29)),
]
rows=[]
for pid,label,length,mass,stiff,damping,extra in design:
    case=copy.deepcopy(base);q=case['physical']
    q.update(thigh_length_scale=length,shank_length_scale=length,thigh_mass_scale=mass,shank_mass_scale=mass,passive_stiffness_nm_rad=[v*stiff for v in q['passive_stiffness_nm_rad']],passive_damping_nms_rad=[v*damping for v in q['passive_damping_nms_rad']]);q.update(extra)
    # Keep metadata identical too for the nominal raw-equivalence check. Identity is external.
    put('patients/'+pid+'/case.json',case)
    patient=dict(patient_id=pid,label=label,experiment='P0',source='source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json',case_path='patients/'+pid+'/case.json',case_sha256=sha(P/'patients'/pid/'case.json'),physical=q,engineering_factors=dict(length=length,mass=mass,stiffness=stiff,damping=damping,extra=extra),range_evidence='EXPLORATORY_ENGINEERING_SENSITIVITY_NOT_CLINICAL_DISTRIBUTION',future_learning_split='RESERVED_PATIENT_TEST_NO_TUNING' if pid in ['P09','P10','P11'] else 'DEVELOPMENT',current_study_outcomes_exposed=True,seed=oldplan['condition']['seed'],prefix=oldplan['condition']['prefix'])
    rows.append(patient)
    cond=dict(name=pid,seed=patient['seed'],prefix=patient['prefix'],patient_id=pid,split=patient['future_learning_split'])
    put(pid+'_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,arms=arms,patient=patient,full_task_integral_includes_shared_prefix=True))
cohort=dict(schema='IHEAR_CROSS_PATIENT_COHORT_V1',registered_unix=time.time(),patients=rows,order=[r['patient_id'] for r in rows],within_patient_order=['B','H150'],patient_identity_is_unit=True,same_seed_for_factor_isolation=True,range_basis='Small symmetric engineering perturbations around frozen model; no clinical percentile interpretation',future_split_note='P09/P10/P11 identities reserved from future training/parameter tuning. They are exposed in this descriptive study; future analysts must not use their outcomes for model selection. New untouched identities required if these outcomes influence learning design.',failure_policy='Retain every model, commissioning, parent and arm failure. B failure does not suppress H150 from an already legal common parent; no patient reselection. Task failure precludes full-task gain; unsafe B precludes qualified relative motion interpretation.',P0='Frozen algorithm/prior/config; original causal commissioning remains; no provided true patient parameters',P1='PROTOCOL_ONLY_NOT_RUN',extra_repeat='At most one cold repeat of earliest complete pair with a clear qualitative qualification boundary; deterministic repeat is not a patient')
put('VIRTUAL_PATIENT_COHORT.json',cohort)
put('PREREGISTRATION.json',dict(registered_unix=time.time(),cohort_sha256=sha(P/'VIRTUAL_PATIENT_COHORT.json'),patient_case_sha256={r['patient_id']:r['case_sha256'] for r in rows},candidate_hashes={a['id']:a['candidate_hash'] for a in arms},frozen_18d_sha256=sha(P/'FROZEN_18D.json'),motion_protocol_sha256=sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json'),task_targets_unchanged=True,original_timing_safety_motion_contracts=True,physics_starts_before_registration=0,no_results_used=True,force_gain_valid_only_full_integral=True,qualification_labels=['TASK_FAIL','ABSOLUTE_SAFETY_FAIL','MOTION_RELATIVE_FAIL','CAUSAL_EXECUTION_FAIL','MODEL_NOT_ADMISSIBLE','COMPLETE_QUALIFIED_PASS']))
(P/'ATTEMPTS.jsonl').touch()
for n in ['VIRTUAL_PATIENT_COHORT.json','PREREGISTRATION.json']:shutil.copy2(P/n,R/n)
print('PREREGISTERED',len(rows),flush=True)
