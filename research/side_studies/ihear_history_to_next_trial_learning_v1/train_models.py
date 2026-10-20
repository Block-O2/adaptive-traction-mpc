"""Train only from complete preregistered development forks. No physics."""
from pathlib import Path
import json,time,hashlib,shutil,sys
import numpy as np
P=Path(__file__).resolve().parent
import history_features as hf
from learning_models import SELECTED,phi
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def margin_of(c):
    if c is None:return None
    margins=[]
    for values in c['burden_ratios'].values():margins.extend([1.1-v for v in values])
    margins.extend([(.5-v)/.5 for v in c['excursion_delta_deg']])
    for v in c['cumulative_ratio']:margins.extend([(1.05-v)/.05,(v-.95)/.05])
    margins.extend([(.5-v)/.5 for v in c['endpoint_abs_delta_deg']])
    margins.extend([(.5-c['phase_boundary_max_delta_deg'])/.5,(.1-c['duration_abs_delta_s'])/.1,(1.25-c['moment_integral_ratio'])/.25])
    # This is a predictive selected-margin head, not a replacement for all original gates.
    return float(min(margins))
def main():
    assert not (P/'models/METHOD_FREEZE.json').exists(),'FROZEN_METHOD_NOT_OVERWRITTEN'
    started=time.time();dataset=[];failures=[];hist=[];firstcost=[];executed=[]
    for patient in ['P00','P05','P08']:
        group='P00R' if patient=='P00' else patient
        result=read(group+'_RESULTS.json');history=read('learning/'+group+'_T1_HISTORY.json')
        h=np.array(history['features'])[SELECTED];hist.append(h);firstcost.append(history['JF_N_s'])
        for r in result['rows']:
            if r['method'] not in ['B','O_MINUS','O_PLUS','R_MINUS','R_PLUS']:continue
            a=hf.encode_action(r['decision']['action']);ex=float(r['absolute_task_execution_qualified'])
            executed.append(dict(patient=patient,h=h.tolist(),a=a.tolist(),success=ex,id=r['id']))
            if not r['complete_task'] or r['J_F_N_s'] is None:
                failures.append(dict(patient=patient,id=r['id'],history=h.tolist(),action=a.tolist(),execution_success=ex,labels=r['labels']));continue
            margin=.1 if r['method']=='B' else margin_of(r.get('motion_comparison'))
            if margin is None:margin=-1.
            if not r.get('complete_qualified',False):margin=min(margin,-.001)
            dataset.append(dict(patient=patient,id=r['id'],h=h.tolist(),a=a.tolist(),JF=r['J_F_N_s'],
                first_JF=history['JF_N_s'],y_cost=r['J_F_N_s']-history['JF_N_s'],motion_margin=margin,execution_success=ex,
                qualified=r.get('complete_qualified',False),history_sha256=history['raw_history_sha256']))
    assert len(hist)==3 and len(dataset)>=9,'INSUFFICIENT_EXECUTED_DATA'
    H=np.asarray([r['h'] for r in dataset]);A=np.asarray([r['a'] for r in dataset]);patients=np.array([r['patient'] for r in dataset])
    mu=np.mean(hist,axis=0);sd=np.maximum(np.std(hist,axis=0),[5.,5.,.1,.1]);Z=(H-mu)/sd
    X=np.array([phi(z,a) for z,a in zip(Z,A)])
    Y=np.array([[r['y_cost'],r['motion_margin'],r['execution_success']] for r in dataset])
    XA=np.array([phi((np.array(r['h'])-mu)/sd,r['a']) for r in executed]);YA=np.array([r['success'] for r in executed]);PA=np.array([r['patient'] for r in executed])
    def fit(mask,execution_mask):
        penalty=np.eye(X.shape[1])*1.;penalty[0,0]=.01
        w=np.linalg.solve(X[mask].T@X[mask]+penalty,X[mask].T@Y[mask])
        w[:,2]=np.linalg.solve(XA[execution_mask].T@XA[execution_mask]+penalty,XA[execution_mask].T@YA[execution_mask])
        return w
    full=fit(np.ones(len(X),bool),np.ones(len(XA),bool));ensemble=[full];loo=[]
    for patient in sorted(set(patients)):
        fitw=fit(patients!=patient,PA!=patient);ensemble.append(fitw);pred=X[patients==patient]@fitw;truth=Y[patients==patient]
        for idx,v,t in zip(np.flatnonzero(patients==patient),pred,truth):loo.append(dict(id=dataset[idx]['id'],patient=patient,predicted=v.tolist(),actual=t.tolist(),error=(v-t).tolist()))
    costfloor=max(.02,float(np.quantile([abs(r['error'][0]) for r in loo],.8)))
    marginfloor=max(.005,float(np.quantile([abs(r['error'][1]) for r in loo],.8)))
    base_drift=[abs(r['y_cost']) for r in dataset if np.all(np.array(r['a'])==0)]
    weights=P/'models/history_models.npz'
    np.savez_compressed(weights,history_mean=mu,history_std=sd,gp_X=np.c_[Z,A],gp_A=np.array([r['a'] for r in executed]),gp_y_cost=Y[:,0],gp_y_margin=Y[:,1],
        execution_success=YA,gp_noise_cost=max(.05,max(base_drift)),gp_scale_cost=max(.2,float(np.std(Y[:,0]))),
        ridge_ensemble=np.array(ensemble),value_cost_error_floor=costfloor,value_margin_error_floor=marginfloor,
        mean_first_JF=np.mean(firstcost),training_patients=3)
    put('models/TRAINING_DATA.json',dict(rows=dataset,failed_or_partial=failures,execution_labels=executed,patient_split='development_only',native_steps_not_independent_samples=True))
    put('models/LEAVE_PATIENT_OUT.json',dict(rows=loo,cost_error_floor_N_s=costfloor,margin_error_floor=marginfloor,
        warning='Three patients cannot establish reliable error calibration; DATA_LIMITED'))
    put('models/TRAINING_RESULTS.json',dict(started_unix=started,finished_unix=time.time(),training_patients=3,independent_parents=3,
        full_action_results=len(dataset),failed_or_partial=len(failures),ridge_solves=4,GP_training_rows=len(dataset),
        methods=['fixed-gain history ILC','separate cost/margin Gaussian processes','ridge history x action ensemble'],
        feature_names=[hf.FEATURE_NAMES[i] for i in SELECTED],interaction_features=8,lambda_ridge=1.,
        hyperparameters='preregistered simple values; no heldout search',data_status='DATA_LIMITED',new_physics_starts=0))
    population=dict(local={'OUTBOUND':dict(mean_force_N=float(mu[0]),tracking_mean_deg=[0.,float(mu[2])]),
        'RETURN':dict(mean_force_N=float(mu[1]),tracking_mean_deg=[0.,float(mu[3])])},raw_history_sha256='POPULATION_MEAN_DEVELOPMENT_ONLY',
        source_patients=['P00','P05','P08'],current_patient_history_consumed=False)
    put('models/POPULATION_HISTORY.json',population)
    put('models/METHOD_FREEZE.json',dict(frozen_unix=time.time(),training_patients=['P00','P05','P08'],
        validation_patients=['V12','V13'],heldout_patients=['U14','U15','U16'],
        model_files={str(f.relative_to(P)):sha(f) for f in [weights,P/'models/TRAINING_DATA.json',P/'models/POPULATION_HISTORY.json',P/'learning_models.py',P/'history_features.py']},
        selection='bounded grid; separate feasibility/motion estimates; uncertain or outside domain => A0',
        no_future_patient_results_consumed=True,original_qualification_gates_unchanged=True))
    print('TRAINED',len(dataset),'rows / 3 patients; DATA_LIMITED',flush=True)
if __name__=='__main__':main()
