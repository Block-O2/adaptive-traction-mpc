"""Freeze new patient identities and the initial experiment before any physics."""
from pathlib import Path
import json,time,hashlib,copy,shutil,sys
import numpy as np
REVIEW=Path(__file__).resolve().parent
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/REVIEW.name
OLD=P.parent/'ihear_cross_patient_b_h150_v1'
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert (P/'BOOTSTRAP_DONE.json').exists()
assert not (P/'COHORT.json').exists(), 'IMMUTABLE_PREREGISTRATION'
assert not (P/'ATTEMPTS.jsonl').exists()
old=json.loads((OLD/'VIRTUAL_PATIENT_COHORT.json').read_text())['patients']
rows=[]
for pid in ['P00','P05','P08']:
    r=copy.deepcopy(next(r for r in old if r['patient_id']==pid));r['split']='development';r['prior_results_exposed']=True
    r['source_identity']=pid;rows.append(r)
    put(r['case_path'],json.loads((OLD/r['case_path']).read_text()))
base=json.loads((OLD/'patients/P00/case.json').read_text())
rng=np.random.default_rng(202610192200)
for pid,split in [('V12','validation'),('V13','validation'),('U14','heldout'),('U15','heldout'),('U16','heldout')]:
    # New engineered identities; sampling family is fixed now, never adjusted to fix failures.
    length=float(rng.uniform(.965,1.035));mass=float(rng.uniform(.85,1.15))
    stiffness=float(rng.uniform(.75,1.25));damping=float(rng.uniform(.75,1.25))
    case=copy.deepcopy(base);q=case['physical']
    q.update(thigh_length_scale=length,shank_length_scale=length,thigh_mass_scale=mass,shank_mass_scale=mass,
        passive_stiffness_nm_rad=[v*stiffness for v in q['passive_stiffness_nm_rad']],
        passive_damping_nms_rad=[v*damping for v in q['passive_damping_nms_rad']])
    path='patients/'+pid+'/case.json';put(path,case)
    rows.append(dict(patient_id=pid,split=split,case_path=path,case_sha256=sha(P/path),seed=old[0]['seed'],prefix=old[0]['prefix'],
        engineering_factors=dict(length=length,mass=mass,stiffness=stiffness,damping=damping),prior_results_exposed=False,
        source_identity='NEW_GENERATED_202610192200',distribution_claim='ENGINEERING_ONLY_NOT_CLINICAL'))
for row in rows:
    row['case_sha256']=sha(P/row['case_path'])
    cond=dict(name=row['patient_id'],seed=row['seed'],prefix=row['prefix'],patient_id=row['patient_id'],split=row['split'])
    put(row['patient_id']+'_TEST_PLAN.json',dict(condition=cond,patient=row,arms=[],fork_after_prefix=1))
put('COHORT.json',dict(registered_unix=time.time(),generation_seed=202610192200,patients=rows,
    historical_12_patient_results_observed=True,old_P09_P11_not_heldout=True,
    split_unit='complete patient identity and all repetitions/actions/prefixes',
    development_order=['P00','P05','P08'],validation_order=['V12','V13'],heldout_order=['U14','U15','U16']))
put('PREREGISTRATION.json',dict(unix=time.time(),cohort_sha256=sha(P/'COHORT.json'),
    hypothesis='First complete B motion identifies burden and lag; bounded local posture adjustment may improve next complete qualified trial versus matched no-history controls.',
    first_action='FROZEN_B_WITH_W1_PREFIX',fixed_comparators=['B','H150'],
    action_family=dict(joint='knee',maximum_abs_delta_deg=.3,locations=[['OUTBOUND',1],['RETURN',3]],
        original_duration_and_outer_pass_velocity=True,original_task_endpoint_and_hold=True),
    ilc='Choose larger mid-progress phase force burden; delta=clip(0.25*(estimated_actual-reference)_knee,+-0.3deg)',
    initial_grid='A0 and +/-0.3deg at each of two allowed locations; history-disabled ILC=A0',
    benefit_threshold_N_s=.01,qualification='All original absolute safety/task/execution plus B-relative motion/fairness gates separately',
    no_partial_cost_ranking=True,budget=80,planned_first_development_starts=9,minimum_development_patients=3,
    no_future_labels=True,no_patient_native_truth_in_history=True,no_automatic_RL=True,
    heldout_results_require_method_freeze=True,physics_before_registration=0))
(P/'ATTEMPTS.jsonl').touch()
for n in ['COHORT.json','PREREGISTRATION.json']:shutil.copy2(P/n,REVIEW/n)
print('REGISTERED',len(rows),flush=True)
