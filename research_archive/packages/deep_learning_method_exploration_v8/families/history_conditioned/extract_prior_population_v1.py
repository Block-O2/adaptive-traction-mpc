"""Approved <=60s, 0-fit/0-physics historical population summary.

Only two old complete qualified H150 contexts. No v8 result or native Human
values are read. Slot labels are joined by exact original task time and phase,
not an ordinal guess. The terminal skip is reconstructed from original count
semantics only after all 0..4 labels and exactly one terminal skip are verified.
"""
from pathlib import Path
import hashlib,json,math,os,sys,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
import numpy as np
from modal_ilc_projection_v1 import extract_executed_slot_statistics,project_slot_history

F=Path(__file__).resolve().parent
OLD=F.parents[2]/'autonomous_learning_smoothness_v7'
ROOT=F.parents[1]


def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()


def extract(ident,group):
    config=OLD/'experiments'/(group+'.json');cfg=read(config)
    case=OLD/cfg['case_path'];case_data=read(case)
    if case_data['cell']['family'] not in ('nominal','light_soft','light_stiff') and not any(s in case.name for s in ('nominal','light')):
        raise ValueError('ONLY_PRIOR_NOMINAL_OR_LIGHT')
    base=OLD/'runtime/source/results'/ident
    paths=[config,case,base/'trace.npz',base/'summary.json',OLD/'runtime/output'/(ident+'_DECISIONS.json'),
        OLD/'runtime/reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'),OLD/'attempts'/(ident+'_RESULT.json'),
        OLD/'history'/(ident+'_CAUSAL_HISTORY.json'),OLD/'attempts'/(ident+'_EXECUTION_BINDING.json')]
    result=read(paths[6]);summary=read(paths[3]);labels=read(paths[4]);lineage=read(paths[5]);binding=read(paths[8])
    if result.get('complete') is not True or result.get('qualified') is not True or summary['status']!='COMPLETE' or lineage['status']!='PASS':raise ValueError('PRIOR_FULL_QUALIFICATION_REQUIRED')
    if result['action'].get('family')!='H150' or any(result['action'].get('legacy',[0.,0.])):raise ValueError('PLAIN_LEGAL_H150_REQUIRED')
    if binding['candidate']['base']!='T':raise ValueError('H150_EXECUTION_BINDING')
    for key in ('posture','early','timing','changes'):
        if binding['candidate'].get(key,[])!=cfg['H150'].get(key,[]):raise ValueError('EXACT_H150_RECIPE_BINDING:'+key)
    with np.load(paths[2],allow_pickle=False) as z:
        ix=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ix]
        if len(ix)<4 or not np.allclose(np.diff(t),.005,atol=1e-8,rtol=0) or not bool(z['terminal_boundary_node'][ix[-1]]):raise ValueError('COMPLETE_5MS_TASK_GRID')
        # These fields are existing observer/reference/measurement exports.
        # Native/evaluation-only Human arrays are deliberately never accessed.
        est=z['estimated_human_state_rad_rad_s'][ix];ref=np.c_[z['reference_q_rad'][ix],z['reference_dq_rad_s'][ix]]
        force=z['physical_cuff_force_world_n'][ix];moment=z['physical_cuff_moment_world_nm'][ix];phase=z['task_phase'][ix]
    if not np.all(np.isfinite(np.c_[t,est,ref,force,moment])):raise ValueError('NONFINITE_CAUSAL_EXPORT')
    commit=next(r for r in summary['task']['phase_transitions'] if r['to']=='COMPLETE')
    if commit['time_s']!=float(t[-1]) or not np.array_equal(commit['estimated_state'],est[-1]) or commit['state_source_time_s']>t[-1]+1e-10:raise ValueError('REAL_CAUSAL_TERMINAL_COMMIT')
    jf=float(np.linalg.norm(force[:-1],axis=1)@np.diff(t));jm=float(np.linalg.norm(moment[:-1],axis=1)@np.diff(t))
    if abs(jf-result['JF'])>1e-6 or abs(jm-result['JM'])>1e-6:raise ValueError('FULL_TASK_ORIGINAL_JF_JM_CLOSURE')
    saved=read(paths[7]);saved_matches=0
    for row in saved:
        k=int(np.searchsorted(t,float(row['time_s'])))
        if k>=len(t) or abs(t[k]-row['time_s'])>1e-9:raise ValueError('SAVED_CAUSAL_TIME_NOT_IN_TRACE')
        for key,value in [('estimated_q_dq',est[k]),('reference_q_dq',ref[k]),('measured_force',force[k]),('measured_moment',moment[k])]:
            if not np.array_equal(np.asarray(row[key]),value):raise ValueError('SAVED_CAUSAL_TRACE_MISMATCH:'+key)
        if row['truth_used'] is not False or row['source_sample_time_s']>row['time_s']+1e-9:raise ValueError('NONCAUSAL_SAVED_ROW')
        saved_matches+=1
    rows=[dict(time_s=float(t[k]),phase=str(phase[k]),estimated_q_dq=est[k].tolist(),reference_q_dq=ref[k].tolist(),truth_used=False) for k in range(len(t))]
    # The original TableInterface creates native_index before increment and
    # stores task_s=physical_now-task_start. The same original decision records
    # request_time_s, phase, and timing_request_id. Require a unique 1e-9 join.
    requests=[];evidence=[];used=set();labels_by_phase={}
    for label in labels['rows']:
        labels_by_phase.setdefault(label['phase'],[]).append(label)
        matches=[(k,d) for k,d in enumerate(summary['decisions']) if d['phase']==label['phase'] and abs(d['decision_request_time_s']-(float(t[0])+label['task_s']))<=1e-9]
        if len(matches)!=1:raise ValueError('NONUNIQUE_OR_MISSING_EXACT_SLOT_REQUEST_JOIN')
        k,d=matches[0]
        if k in used:raise ValueError('DUPLICATED_SLOT_REQUEST_JOIN')
        used.add(k);slot=int(label['native_index'])
        requests.append(dict(request_id=d['timing_request_id'],phase=d['phase'],slot=slot,public_phase_goal_rad=d['terminal_reference_selection']['reference_target_rad']))
        evidence.append(dict(decision_index=k,request_id=d['timing_request_id'],phase=d['phase'],slot=slot,
            label_task_s=label['task_s'],decision_request_time_s=d['decision_request_time_s'],join='saved native_index + exact phase/task_s',
            terminal_goal=d['terminal_reference_selection']['reference_target_rad']))
    for ph in ('OUTBOUND','RETURN'):
        if [int(r['native_index']) for r in labels_by_phase.get(ph,[])]!=list(range(5)):raise ValueError('ALL_FIVE_ORIGINAL_COUNTED_SLOT_LABELS_REQUIRED:'+ph)
        unjoined=[(k,d) for k,d in enumerate(summary['decisions']) if k not in used and d['phase']==ph]
        skips=[r for r in labels['skipped'] if r['phase']==ph]
        if len(unjoined)!=1 or len(skips)!=1 or skips[0]['reason']!='NATIVE_TERMINAL_OWNERSHIP':raise ValueError('EXACT_TERMINAL_SKIP_PROOF_REQUIRED:'+ph)
        k,d=unjoined[0]
        if k!=max(j for j,x in enumerate(summary['decisions']) if x['phase']==ph):raise ValueError('TERMINAL_SKIP_MUST_BE_LAST_REQUEST')
        requests.append(dict(request_id=d['timing_request_id'],phase=ph,slot=5,public_phase_goal_rad=d['terminal_reference_selection']['reference_target_rad']))
        evidence.append(dict(decision_index=k,request_id=d['timing_request_id'],phase=ph,slot=5,
            join='source-proven unchanged count=5 after saved 0..4; exactly one native-terminal skip; no increment on skip',
            terminal_goal=d['terminal_reference_selection']['reference_target_rad']))
        used.add(k)
    for k,d in enumerate(summary['decisions']):
        if k not in used:
            if d['phase']!='HOLD':raise ValueError('UNRESOLVED_REAL_REQUEST')
            requests.append(dict(request_id=d['timing_request_id'],phase='HOLD',slot=0,public_phase_goal_rad=d['terminal_reference_selection']['reference_target_rad']))
    statistics=extract_executed_slot_statistics(rows,requests,summary,lineage)
    if [r['slot'] for r in statistics]!=list(range(6)):raise ValueError('ALL_SIX_EXECUTED_RETURN_WINDOWS_REQUIRED')
    return dict(id=ident,group=group,case_path=str(case),case_sha256=sha(case),qualified=True,
        input_sources={str(p):sha(p) for p in paths},source_fields=['estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','physical_cuff_force_world_n','physical_cuff_moment_world_nm','time_s','task_phase','terminal_boundary_node'],
        boundary_nodes=len(t),saved_causal_rows_exactly_matched=saved_matches,JF_N_s=jf,JM_Nm_s=jm,
        request_slot_evidence=evidence,slot_statistics=statistics,truth_used_for_features=False,
        action=result['action'],H150_recipe=cfg['H150'],identity_scope='one historical exposed physical context; no new independent patient claim')


def main():
    started=time.time();cpu=time.process_time()
    out=F/'PRIOR_NOMINAL_LIGHT_H150_POPULATION_V1.json'
    if out.exists():raise RuntimeError('UNIQUE_POPULATION_ALREADY_FROZEN_DO_NOT_OVERWRITE')
    cases=[extract('PFXV02_H150_FIXED','PFXV02'),extract('CFACTORL01_LATE_H150','CFACTORL01')]
    if time.process_time()-cpu>60 or time.time()-started>60:raise TimeoutError('APPROVED_60S_READONLY_BUDGET')
    sources=[OLD/'source/v7_worker_v2.py',OLD/'runtime/control/campaign_v6.py',OLD/'runtime/code/interfaces.py',OLD/'runtime/deps/coordination_adapter.py',F/'modal_ilc_projection_v1.py',Path(__file__)]
    value=dict(schema='PRIOR_QUALIFIED_H150_SLOT_POPULATION_V1',status='FROZEN_PRIOR_ONLY_NO_FIT_NO_PHYSICS',frozen_unix=time.time(),
        frozen_before_current_T1=True,current_T1_scope='future separately authorized CONTINUOUS_ILC_RETURN_X3_V1; not B-only engineering',
        source_context_count=2,source_complete_trial_count=2,source_RETURN_windows=12,
        aggregation='Concatenation of both six-slot histories; exact observed durations weight the same frozen projection. No synthetic patient or zero imputation.',
        slot_statistics=[r for c in cases for r in c['slot_statistics']],sources=cases,
        excluded_known_ineligible=['H150N01_H150_FIXED: excursion gate FAIL','H150L01_H150_FIXED: excursion gate FAIL','EARLYN01_LATE_H150: excursion gate FAIL','EARLYL01_LATE_H150: excursion gate FAIL'],
        excluded_all_v8_results=True,excluded_heavy_histories=True,no_new_heavy_T1_T2_read=True,
        source_code_sha256={str(p):sha(p) for p in sources},model_fits=0,physics_steps=0,cpu_s=time.process_time()-cpu,wall_s=time.time()-started,
        limitation='Two old exposed nominal/light contexts with different legal prefixes/case geometry, not independent patient validation or a calibrated population prior.')
    value['frozen_disabled_projection']=project_slot_history(value['slot_statistics'],gain=.25)
    with out.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(dict(output=str(out),sha256=sha(out),contexts=2,windows=12,cpu_s=value['cpu_s'],disabled_x3=value['frozen_disabled_projection']['x3'])))


if __name__=='__main__':main()
