"""Availability audit only: never emits supervised rows or invokes a learner.

Exact frozen old48/A3 scoped39 inputs and already-closed original traces only.
Future trace fields are inspected for label availability/closure, never input.
"""
from pathlib import Path
import hashlib,json,resource,time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPO=ROOT.parent
DATA='families/critic_value/coverage_risk_v2/data/ACTUAL_COVERAGE_DATASET_V1.json'
DATA_SHA='e7a54dd7d3d39f0ab94cec45ceea284d6efec51d186ab74e46ff2335e82b79e0'
SCOPED='families/critic_value/coverage_state_v3/data/SCOPED_OUT0_STATES_V1.json'
SCOPED_SHA='7a1ba773b37686e13571d6c4aa4dfa31f180725e2ec7ee464170ef6258e3f68d'
HORIZONS=(.5,1.,2.,4.,8.,12.,16.)
FIELDS=('stage','time_s','task_phase','terminal_boundary_node','estimated_human_state_rad_rad_s',
    'reference_q_rad','reference_dq_rad_s','physical_cuff_force_world_n','physical_cuff_moment_world_nm')

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(x,s):
    if not x:raise ValueError(s)

def main():
    started=time.monotonic();cpu=time.process_time();out=HERE/'SOURCE_AVAILABILITY_AUDIT_V1.json'
    need(not out.exists(),'PRESERVE_EXISTING_AUDIT')
    need(sha(ROOT/DATA)==DATA_SHA and sha(ROOT/SCOPED)==SCOPED_SHA,'EXACT_INPUT_DATA_BYTES')
    data=read(ROOT/DATA);scoped={r['group_evaluation_only']:r for r in read(ROOT/SCOPED)['records']}
    profiles=read(ROOT/'families/critic_value/coverage_state_v3/fit_run_v1/A3_FROZEN_BUNDLE_V1.json')
    records=[];groups=[];fail=[]
    for group in sorted({r['group'] for r in data['rows']}):
        need(time.monotonic()-started<60.,'AUDIT_ONLY_60S')
        rows=[r for r in data['rows'] if r['group']==group];P=REPO/Path(rows[0]['source_result']).parts[0]
        done=read(P/'jobs'/group/'WORKER_DONE.json');sup=read(P/'owned'/(group+'_SUPERVISOR_END.json'));exit_=read(P/'owned'/(group+'_EXIT.json'))
        need(done['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS' and done['all_children_joined'] is True,'CLOSED_DONE')
        need(sup['state']=='STOP' and sup['worker_exit_code']==0 and sup['survivors']==[] and exit_.get('active_child') is None,'CLOSED_OWNER')
        config_path=P/'experiments'/(group+'.json');config=read(config_path);source=read(P/'jobs'/group/'SOURCE_MANIFEST.json')
        need(source['config_sha256']==sha(config_path),'ORIGINAL_CONFIG_SHA')
        sr=scoped[group];rawpath=Path(sr['source_payload_path']);raw=read(rawpath)
        need(sha(rawpath)==sr['source_payload_file_sha256'],'ORIGINAL_OUT0_PAYLOAD_SHA')
        body={k:v for k,v in raw.items() if k!='causal_payload_sha256'}
        need(digest(body)==raw['causal_payload_sha256']==sr['source_payload_body_checksum'],'ORIGINAL_OUT0_BODY_CHECKSUM')
        need(raw['task_s']==0. and raw['phase']=='OUTBOUND' and raw['hidden_or_future_inputs_used'] is False and raw['model_prediction_or_observe_calls']==0 and raw['model_vector_valid'] is False,'REGISTERED_SCOPED_OUT0_ONLY')
        need(raw['capture_position']=='parent request boundary BEFORE fork loop/candidate selection/control mutation','PREACTION_CAPTURE')
        values=dict(zip(raw['feature_names'],raw['features']));subset=sr['subsets']['WRENCH39']
        need(len(subset['feature_names'])==39 and subset['features']==[values[n] for n in subset['feature_names']],'EXACT_LEGAL39_SUBSET')
        matches=[(proof,paths) for proof,paths in zip(profiles['input_source_profiles'],profiles['input_source_profile_paths']) if paths['callback']=='source/'+config['worker']]
        need(len(matches)==1,'FROZEN_A3_SOURCE_PROFILE')
        proof,paths=matches[0]
        need(all(sha(P/p)==proof[k]==source['files'][p] for k,p in paths.items()),'ORIGINAL_SOURCE_PROFILE_IDENTITY')
        first_common=None;parent={r['parent_evaluation_only']['snapshot_full_hash'] for r in rows}
        need(len(parent)==1,'SAME_REAL_PARENT')
        groups.append(dict(group=group,case_sha256=config['case_sha256'],parent_full_hash=next(iter(parent)),rows=len(rows),
            source_payload_path=str(rawpath),source_payload_sha256=sha(rawpath),body_checksum=raw['causal_payload_sha256'],
            legal39_object_sha256=digest(subset),config_path=str(config_path),config_sha256=sha(config_path),
            source_manifest_path=str(P/'jobs'/group/'SOURCE_MANIFEST.json'),source_manifest_sha256=sha(P/'jobs'/group/'SOURCE_MANIFEST.json'),
            source_profile=proof,source_profile_paths=paths,available_tags=[r['action_tag_evaluation_only'] for r in rows],
            missing_tags=[m['tag'] for m in data['menu'] if m['recipe_sha256'] not in {r['action_recipe_sha256'] for r in rows}]))
        expected=np.asarray([values[n] for n in ['estimated_q_hip','estimated_q_knee','estimated_dq_hip','estimated_dq_knee',
            'request_reference_q_hip','request_reference_q_knee','request_reference_dq_hip','request_reference_dq_knee']+
            ['measured_force_world_'+a for a in 'xyz']+['measured_moment_world_'+a for a in 'xyz']],float)
        for row in rows:
            need(time.monotonic()-started<60.,'AUDIT_ONLY_60S')
            ident=row['id'];rp=REPO/row['source_result'];result=read(rp);trace=P/'runtime/source/results'/ident/'trace.npz'
            need(result['complete'] is True and result.get('error') is None,'EXACT48_COMPLETE_ONLY')
            with np.load(trace,allow_pickle=False) as archive:z={k:archive[k] for k in FIELDS}
            ids=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ids];y=np.c_[z['estimated_human_state_rad_rad_s'][ids],z['reference_q_rad'][ids],z['reference_dq_rad_s'][ids],z['physical_cuff_force_world_n'][ids],z['physical_cuff_moment_world_nm'][ids]]
            initial_error=float(np.max(np.abs(y[0]-expected)))
            need(initial_error==0. and float(t[0])==float(raw['physical_s']),'FIRST_TASK_IS_ORIGINAL_COMMON_OUT0')
            need(np.all(np.isfinite(y)) and abs(float(np.max(np.abs(np.diff(t)-.005))))<2e-9,'FINITE_5MS_TRACE')
            if first_common is None:first_common=y[0].copy()
            need(np.array_equal(first_common,y[0]),'COMMON_INITIAL14_B_VS_ACTION')
            availability={}
            for horizon in HORIZONS:
                endpoint=int(round(horizon/.005));available=endpoint<len(t)
                if available:need(abs(float(t[endpoint]-t[0])-horizon)<2e-8,'EXACT_CLOCK_WINDOW_ENDPOINT')
                availability[str(horizon)]=dict(available=bool(available),TASK_endpoint_index=endpoint if available else None,
                    actual_end_clock_error_s=float(t[endpoint]-t[0]-horizon) if available else None,
                    terminal14_fields_finite=bool(np.all(np.isfinite(y[endpoint]))) if available else None,
                    JF_JM_complete_boundary_window_available=bool(available))
            force=np.linalg.norm(y[:,8:11],axis=1);moment=np.linalg.norm(y[:,11:14],axis=1)
            # Original analyze_matched.phasecost uses left quadrature.
            jf=float(np.sum(force[:-1]*np.diff(t)))
            jm=float(np.sum(moment[:-1]*np.diff(t)))
            need(abs(jf-result['JF'])<1e-6 and abs(jm-result['JM'])<1e-6,'ORIGINAL_FULL_JF_JM_CLOSURE')
            rec=dict(id=ident,group=group,recipe_sha256=row['action_recipe_sha256'],tag=row['action_tag_evaluation_only'],
                source_result_path=str(rp),source_result_sha256=sha(rp),trace_path=str(trace),trace_sha256=sha(trace),
                first_TASK_global_index=int(ids[0]),first_TASK_physical_s=float(t[0]),first_TASK_initial14_maxabs_error=initial_error,
                common_initial14_sha256=digest(y[0].tolist()),TASK_node_count=len(ids),TASK_duration_s=float(t[-1]-t[0]),
                task_grid_maxabs_dt_error_s=float(np.max(np.abs(np.diff(t)-.005))),terminal_boundary_present=bool(z['terminal_boundary_node'][ids[-1]]),
                complete=True,original_qualified=result['qualified'],eligible_for_short_window_prediction_even_if_motion_fail=True,
                original_full_cost_closure_error={'JF':jf-result['JF'],'JM':jm-result['JM']},horizon_availability=availability,
                evaluation_only_truth_arrays_read=False,target_values_emitted=False)
            records.append(rec)
    counts=dict(actual_rows=len(records),parent_contexts=len(groups),distinct_case_sha256=len({g['case_sha256'] for g in groups}),
        full_five_recipe_contexts=sum(g['rows']==5 for g in groups),missing_menu_labels=sum(len(g['missing_tags']) for g in groups),
        partial_rows_in_frozen48=0,original_qualified=sum(r['original_qualified'] for r in records),
        complete_original_motion_failed=sum(not r['original_qualified'] for r in records),
        aligned_common_OUT0_rows=sum(r['first_TASK_initial14_maxabs_error']==0 for r in records),
        horizon_available_rows={str(h):sum(r['horizon_availability'][str(h)]['available'] for r in records) for h in HORIZONS})
    report=dict(schema='v8.E.common_out0_source_availability_audit.v1',status='PASS_SOURCE_ALIGNMENT_AND_LABEL_AVAILABILITY_ONLY',
        source_data_path=DATA,source_data_sha256=DATA_SHA,source_scoped_path=SCOPED,source_scoped_sha256=SCOPED_SHA,
        source_audit_script_sha256=sha(Path(__file__)),counts=counts,groups=groups,rows_availability_only=records,
        trace_field_read_allowlist=list(FIELDS),supervised_dataset_built=False,supervised_target_values_emitted=False,
        raw_gzip_or_command_stream_read=False,model_initializations=0,model_calls=0,fit=0,physics=0,sealed_reads=0,active_L2_reads=0,
        wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],counts=counts,wall_s=report['wall_s'],cpu_s=report['cpu_s'])))

if __name__=='__main__':main()
