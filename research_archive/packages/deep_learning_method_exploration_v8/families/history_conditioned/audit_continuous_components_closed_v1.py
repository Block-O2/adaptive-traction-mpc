"""Completed-audit supplement: actual references, BO heads/selection, prior.

No evaluator rerun, model import, fit or prediction. Only original stored
predictions are checked arithmetically; pure margin formula is AST-extracted.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
GROUP='V8CONTILC01'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def main():
    start=time.monotonic();cpu=time.process_time()
    path=HERE/'audit'/f'{GROUP}_INDEPENDENT_CONTINUOUS_V1/RESULT.json'
    assert sha(path)=='4f93cd91653986bcda69b1949a58a99115870b9efbf9b1eb1de53fe6d07a5ced'
    result=read(path);assert result['status']=='INDEPENDENT_CONTINUOUS_RAW_AUDIT_PASS'
    closure=read(path.parent/'START.json')['closure'];assert closure['status']=='CLOSED'
    import numpy as np
    records={Path(item['path']).name:item for item in result['BO_original_artifacts_only']}
    bundle_item=next(v for k,v in records.items() if k.endswith('_OBSERVATION_BUNDLE.json'))
    decision_item=next(v for k,v in records.items() if k.endswith('_DECISION.json'))
    for item in (bundle_item,decision_item):assert sha(ROOT/item['path'])==item['sha256']
    bundle=bundle_item['record'];decision=decision_item['record'];errors=[]
    if digest(bundle)!=decision['input_sha256']:errors.append('EXACT_BUNDLE_DIGEST')
    if decision['owner_before_hash']!=decision['owner_after_hash'] or decision['owner_before_hash']!=bundle['parent_snapshot_sha256']:errors.append('FIT_PARENT_HASH')
    by_id={r['id']:r for r in result['trials']};strong=by_id[GROUP+'_T2_H150_T3_H150'];baseline=GROUP+'_T2_H150_T3_B'
    protocol=read(ROOT/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json')
    tree=ast.parse((HERE/'c2b_evidence_bundle_v2.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='motion_margins')
    namespace={'math':math,'EvidenceError':ValueError};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<pure original margin expression only>','exec'),namespace)
    base_measure=read(ROOT/'runtime/reports'/f'{baseline}_MEASURED.json');observations=[]
    zero=GROUP+'_T2_H150_T3_ZERO_MODAL'
    with np.load(ROOT/'runtime/source/results'/zero/'trace.npz',allow_pickle=False) as f:zt=f['time_s'];zref=f['reference_q_rad']
    for observation in bundle['observations']:
        ident=observation['id'];trial=by_id[ident];bad=[]
        if abs(observation['delta_JF_N_s']-(trial['JF_N_s']-strong['JF_N_s']))>1e-10 or abs(observation['delta_JM_Nm_s']-(trial['JM_Nm_s']-strong['JM_Nm_s']))>1e-10:bad.append('INDEPENDENT_JF_JM_LABEL')
        if observation['qualified']!=trial['independent_qualified']:bad.append('INDEPENDENT_QUALIFICATION')
        snapshot=read(ROOT/'runtime/reports'/f'{ident}_SNAPSHOT.json')
        if snapshot['hash']!=bundle['parent_snapshot_sha256']:bad.append('SAME_FULL_PARENT')
        cached=read(ROOT/'runtime/reports'/f'{ident}_MEASURED.json')
        margin=namespace['motion_margins'](cached,base_measure,protocol)
        if set(margin)!=set(observation['motion_margins']) or any(abs(margin[k]-observation['motion_margins'][k])>1e-12 for k in margin):bad.append('COMPONENT_MARGIN_LABEL')
        with np.load(ROOT/'runtime/source/results'/ident/'trace.npz',allow_pickle=False) as f:
            t=f['time_s'];ref=f['reference_q_rad'];indices=np.clip(np.searchsorted(zt,t),0,len(zt)-1);left=np.maximum(indices-1,0);indices=np.where(abs(zt[left]-t)<abs(zt[indices]-t),left,indices);common=abs(zt[indices]-t)<1e-8
            difference=float(np.max(abs(ref[common]-zref[indices[common]]),initial=0.))
        windows=[]
        if observation['x3']!=0.:
            summary=read(ROOT/'runtime/source/results'/ident/'summary.json');lineage=read(ROOT/'runtime/reports'/f'{ident}_EXECUTED_RESIDUAL_RECEIPTS.json');owners={r['decision_index']:r for r in lineage['rows']}
            for row in summary['learning_records']:
                meta=row.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')
                if meta is None:continue
                changed=np.max(abs(np.asarray(meta['proposed_target_rad'])-np.asarray(meta['original_target_rad'])))>1e-12
                if not changed:continue
                own=owners[row['decision_index']];good=meta['status']=='ACCEPTED' and row.get('selected_plan_activated') is True and own['actual_native_steps']>0 and np.allclose(row['selected_plan']['target_q_rad'],meta['proposed_target_rad'],atol=1e-12,rtol=0)
                windows.append(dict(decision_index=row['decision_index'],accepted_activated_selected_target_and_positive_native=bool(good),actual_native_steps=own['actual_native_steps']))
            if not windows or not all(w['accepted_activated_selected_target_and_positive_native'] for w in windows) or difference<=1e-12:bad.append('ACTUAL_REFERENCE_NOT_JUST_PROPOSAL')
        observations.append(dict(id=ident,x3=observation['x3'],delta_JF=observation['delta_JF_N_s'],delta_JM=observation['delta_JM_Nm_s'],original_qualified=trial['independent_qualified'],reference_maxdiff_rad_vs_zero=difference,actual_executed_windows=windows,minimum_actual_motion_margin=min(margin.values()),errors=bad));errors+=bad
    grid=[];names=decision['head_names'];best=decision['best_observed_qualified']['delta_JF_N_s'];center=next(o for o in bundle['observations'] if o['x3']==0.)
    for index,stored in enumerate(decision['grid_audit']):
        q=stored['x3'];upperF=[];upperM=[];lower=[];reasons=[]
        for model,predictions in decision['predictions'].items():
            pred=predictions[index];assert pred['x3']==q
            upperF.append(pred['mean'][names[0]]+2*pred['spread'][names[0]]);upperM.append(pred['mean'][names[1]]+2*pred['spread'][names[1]])
            lower += [pred['mean'][n]-2*pred['spread'][n] for n in names[2:]]
            if q==0. and (abs(pred['mean'][names[0]])>1e-12 or abs(pred['mean'][names[1]])>1e-12 or any(abs(pred['mean'][n]-center['motion_margins'][n])>1e-12 for n in names[2:])):errors.append('ZERO_ANCHOR:'+model)
        if any(abs(q-x)<=1e-12 for x in bundle['attempted_x3']):reasons.append('ALREADY_ATTEMPTED_SEMANTIC_X3')
        if max(upperF)>best-.01:reasons.append('NO_ALL_MODEL_CONSERVATIVE_FORCE_INCREMENT')
        if max(upperM)>0:reasons.append('JM_COMPONENT_RISK')
        if min(lower)<0:reasons.append('ORIGINAL_MOTION_COMPONENT_RISK')
        if reasons!=stored['reasons'] or (not reasons)!=stored['eligible']:errors.append('PURE_STORED_GRID_RULE')
        grid.append(dict(x3=q,reasons=reasons,eligible=not reasons))
    if decision['status']!='ABSTAIN' or any(g['eligible'] for g in grid) or any(i.endswith('_BO_V2_NEW') for i in closure['ids']):errors.append('ABSTAIN_OR_NO_NEW_PHYSICS')
    receipts=[v['record'] for k,v in records.items() if 'FIT_RECEIPT_' in k];indices=sorted(r['index'] for r in receipts)
    if indices!=list(range(1,43)) or decision['fit_matrix_solves']!=42 or decision['scalar_heads']!=47:errors.append('ACTUAL_FIT_RECEIPT_COUNTS')
    prior=HERE/'PRIOR_NOMINAL_LIGHT_H150_POPULATION_V1.json'
    if sha(prior)!='a6352b665f0e901f8c11073469d39bf3fd6fe01e8af0fe424d8b4741ff6ab596':errors.append('PRIOR_SHA_CHANGED')
    proj_tree=ast.parse((HERE/'modal_ilc_projection_v1.py').read_text());nodes=[n for n in proj_tree.body if isinstance(n,ast.FunctionDef) and n.name in ('return_relative_basis_deg','project_slot_history')];space={'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pure prior projection>','exec'),space)
    prior_update=space['project_slot_history'](read(prior)['slot_statistics'],gain=.25)
    if abs(prior_update['x3']-result['T3_causal_history']['T3_frozen_decisions']['disabled']['x3'])>1e-12:errors.append('FROZEN_POPULATION_DISABLED_PROJECTION')
    report=dict(status='INDEPENDENT_COMPONENT_SUPPLEMENT_PASS' if not errors else 'REVIEW_REQUIRED',errors=errors,observations=observations,stored_prediction_arithmetic_only_grid=grid,BO_status=decision['status'],BO_reason=decision['reason'],original_BO_fit_matrix_solves=42,original_BO_output_heads_per_solve=47,original_BO_scalar_head_solutions=1974,original_BO_fits_are_not_audit_fit= True,original_BO_numerical_fit_CPU_s=decision['cpu_s'],original_BO_extraction_plus_fit_CPU_s=decision['extraction_plus_fit_cpu_s'],original_BO_extraction_plus_fit_wall_s=decision['extraction_plus_fit_wall_s'],prior_disabled_x3=prior_update['x3'],prior_fullrecipe_limitation='Fixed heterogeneous prior: nominal earlyH150 donor plus light lateH150 donor; same H150 base/RETURN component, not identical complete recipes and not unconditional same-action value labels',total_new_native_steps_observed=result['observed_total_new_native_steps'],raw_task_archive_native_rows=sum(t['raw_archive_native_count'] for t in result['trials']),common_prefix_rows_not_paid_again=440,actual_original_main_inverse_dynamics_API_delta_sum=sum(t['delta']['actual_new_main_model_calls'] for t in result['trials']),new_audit_model_import_fit_prediction_physics=0,wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu,source_sha256=sha(__file__))
    output=path.parent/'COMPONENT_SUPPLEMENT_V1.json'
    with output.open('x') as stream:json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status=report['status'],sha256=sha(output),wall_s=report['wall_s'],CPU_s=report['CPU_s'],errors=errors)))


if __name__=='__main__':main()
