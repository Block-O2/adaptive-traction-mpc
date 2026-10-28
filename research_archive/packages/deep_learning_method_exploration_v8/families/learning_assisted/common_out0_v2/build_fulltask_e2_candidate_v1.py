"""One-shot approved full-TASK E2 data build. SOURCE_ONLY until separate approval.

No learner/runtime import. Future estimated/reference/wrench values are labels.
An existing output directory (including a failed attempt) forbids another run.
"""
from pathlib import Path
import argparse,hashlib,json,os,platform,resource,signal,sys,time,traceback

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
ACTIVATION='deep_learning_method_exploration_v8_20261027T032540Z'
STOP=1793114740.0
OUT_REL='families/learning_assisted/common_out0_v2/data/fulltask_e2_v1'
MANIFEST_REL='families/learning_assisted/common_out0_v2/BUILD_E2_SOURCE_MANIFEST_V1.json'
BUILD_CONTRACT_REL='families/learning_assisted/common_out0_v2/BUILD_E2_FROZEN_CONTRACT_V1.json'
AUDIT_REL='families/learning_assisted/common_out0_v2/SOURCE_AVAILABILITY_AUDIT_V1.json'
FIELDS=('stage','time_s','task_phase','terminal_boundary_node','estimated_human_state_rad_rad_s',
        'reference_q_rad','reference_dq_rad_s','physical_cuff_force_world_n','physical_cuff_moment_world_nm')
HORIZONS=(.5,1.,2.,4.,8.,12.,16.,19.03)
IDENTITY_REL='families/learning_assisted/common_out0_v2/E2_ORIGINAL48_SOURCE_IDENTITY_ALLOWLIST_PROPOSED_V1.json'
F1_INDEX_REL='families/learning_assisted/common_out0_v2/data/build_v1/INDEX.json'
HARD=('force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance',
      'true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation')

def need(test,reason):
    if not test:raise ValueError(reason)
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write_new(path,obj):
    with Path(path).open('x') as f:
        json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

class Reader:
    def __init__(self,root,deadline):self.root=root;self.repo=root.parent;self.deadline=deadline;self.files={};self.json_reads=0;self.traces=0
    def check(self):need(time.monotonic()<self.deadline and time.time()<STOP,'ORIGINAL_BUILD_OR_GLOBAL_DEADLINE')
    def path(self,path):
        p=Path(path);p=(self.root/p).resolve() if not p.is_absolute() else p.resolve()
        need(p.is_relative_to(self.root) or p.is_relative_to(self.repo/'autonomous_learning_smoothness_v7'),'OUTSIDE_EXACT_OLD_PACKAGES')
        need(not any(s in str(p).lower() for s in ('/sealed/','_val_','validation_payload','validation_outcome','/current.json','v8op01')),'UNREGISTERED_SEALED_ACTIVE_OR_PG_SOURCE')
        return p
    def hash(self,path,expected=None):
        self.check();p=self.path(path);value=sha(p)
        if expected is not None:need(value==expected,'ORIGINAL_SOURCE_SHA:'+str(p))
        key=str(p.relative_to(self.repo))
        if key in self.files:need(self.files[key]==value,'SOURCE_CHANGED_DURING_BUILD:'+key)
        self.files[key]=value;return value
    def json(self,path,expected=None):
        self.hash(path,expected);self.json_reads+=1;return load(self.path(path))
    def stable(self):
        for relative,expected in list(self.files.items()):self.hash(self.repo/relative,expected)

def original_events(reader,root,ids):
    found={}
    with (root/'runtime/ATTEMPTS.jsonl').open('rb') as f:
        for raw in f:
            event=json.loads(raw)
            if event.get('id') not in ids or event.get('event') not in ('START','END'):continue
            key=event['id']+'|'+event['event'];need(key not in found,'DUPLICATE_ORIGINAL_EVENT')
            found[key]=dict(record=event,raw_line_without_newline_sha256=hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest(),canonical_record_sha256=digest(event))
    need(set(found)=={ident+'|'+kind for ident in ids for kind in ('START','END')},'MISSING_ORIGINAL_START_END')
    for ident in ids:
        end=found[ident+'|END']['record'];need(end.get('joined') is True and end.get('returncode')==0 and end.get('parent_hash_equal') is True,'ORIGINAL_CHILD_NOT_JOINED_OR_PARENT_CHANGED')
    return found

def closed(reader,P,group):
    done=reader.json(P/'jobs'/group/'WORKER_DONE.json');sup=reader.json(P/'owned'/(group+'_SUPERVISOR_END.json'));exit_=reader.json(P/'owned'/(group+'_EXIT.json'))
    need(done.get('status')=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS' and done.get('all_children_joined') is True,'OLD_JOB_NOT_CLEAN_DONE')
    need(sup.get('state')=='STOP' and sup.get('worker_exit_code')==0 and sup.get('survivors')==[] and exit_.get('active_child') is None,'OLD_SUPERVISOR_OR_EXIT_NOT_CLOSED')
    need(sup.get('known_owned'),'ORIGINAL_PID_STARTTICKS_EVIDENCE_REQUIRED')
    for old in sup['known_owned'].values():
        proc=Path('/proc')/str(old['pid'])/'stat'
        if proc.exists():
            fields=proc.read_text().rsplit(')',1)[1].split()
            need(int(fields[19])!=int(old['start_ticks']),'ORIGINAL_OWNED_PID_STARTTICKS_STILL_PRESENT')
    need(reader.json(P/'audit'/(group+'_PARENT_RAW_GATE.json'))['status']=='PASS','ORIGINAL_PARENT_RAW_GATE')

def perform(reader,out,approval,source_manifest,np):
    from common_out0_interface_v1 import FEATURE_NAMES,initial14
    root=reader.root;audit=reader.json(root/AUDIT_REL);contract=reader.json(root/BUILD_CONTRACT_REL)
    need(contract['id']=='E_COMMON_OUT0_FULLTASK_E2_BUILD_V1' and contract['proposed_output_directory']==OUT_REL,'EXACT_BUILD_CONTRACT')
    need(contract['read_allowlist']==list(FIELDS),'EXACT_FROZEN_TRACE_ALLOWLIST')
    need(sha(root/AUDIT_REL)==contract['availability_audit_SHA'],'CONTRACT_AUDIT_SHA')
    identities=reader.json(root/IDENTITY_REL,contract['original48_identity_allowlist_sha256']);identity_by_id={r['id']:r for r in identities['rows']}
    f1=reader.json(root/F1_INDEX_REL,contract['F1_index_sha256']);f1_by_id={r['id']:r for r in f1['rows']}
    need(len(identity_by_id)==len(f1_by_id)==48,'EXACT_PRIOR48_IDENTITIES')
    experiment=reader.json(root/'families/learning_assisted/common_out0_v2/COMMON_OUT0_EXPERIMENT_CONTRACT_V1.json',contract['input_contract_SHA'])
    data=reader.json(root/audit['source_data_path'],audit['source_data_sha256']);scoped=reader.json(root/audit['source_scoped_path'],audit['source_scoped_sha256'])
    byscope={r['group_evaluation_only']:r for r in scoped['records']};byrow={r['id']:r for r in data['rows']};byaudit={r['id']:r for r in audit['rows_availability_only']}
    need(len(data['rows'])==len(byrow)==len(byaudit)==48,'EXACT48_UNIQUE_PHYSICAL_ROWS')
    menu=data['menu'];need([m['tag'] for m in menu]==['B','LATE_H150','EARLY_H150','LATE_PHASE','EARLY_PHASE'],'EXACT_FIVE_MENU')
    need([m['recipe_sha256'] for m in menu]==[m['recipe_sha256'] for m in experiment['inputs']['full_recipe_permission']],'REGISTERED_FULL_RECIPE_HASHES')
    records=[];dense=[];costs=[];clocks=[];endpoints=[];windows=[];events_all={};group_index=[]
    for g in audit['groups']:
        reader.check();group=g['group'];rows=[r for r in data['rows'] if r['group']==group]
        P=reader.path(g['config_path']).parents[1];closed(reader,P,group)
        config=reader.json(g['config_path'],g['config_sha256']);source=reader.json(g['source_manifest_path'],g['source_manifest_sha256'])
        need(source['config_sha256']==g['config_sha256'] and config['group']==group,'EXACT_ORIGINAL_CONFIG')
        reader.hash(P/config['case_path'],config['case_sha256'])
        for role,rel in g['source_profile_paths'].items():need(reader.hash(P/rel,g['source_profile'][role])==source['files'][rel],'ORIGINAL_CAPTURE_SOURCE_PROFILE')
        raw=reader.json(g['source_payload_path'],g['source_payload_sha256']);body={k:v for k,v in raw.items() if k!='causal_payload_sha256'}
        need(digest(body)==raw['causal_payload_sha256']==g['body_checksum'],'ORIGINAL_RAW_BODY_CHECKSUM')
        need(raw['schema']=='ihear.causal_human_context.v1.77d' and raw['task_s']==0. and raw['phase']=='OUTBOUND' and raw['model_vector_valid'] is False,'ORIGINAL_OUT0_NOT_UPGRADED77')
        need(raw['hidden_or_future_inputs_used'] is False and raw['model_prediction_or_observe_calls']==0 and raw['capture_position']=='parent request boundary BEFORE fork loop/candidate selection/control mutation','ORIGINAL_PREACTION_CAUSAL_PERMISSION')
        sr=byscope[group];subset=sr['subsets']['WRENCH39'];values=dict(zip(raw['feature_names'],raw['features']))
        need(subset['feature_names']==FEATURE_NAMES and subset['features']==[values[n] for n in FEATURE_NAMES] and digest(subset)==g['legal39_object_sha256'],'EXACT_LEGAL39_VALUES_ORDER')
        need(sr['checks'] and all(sr['checks'].values()) and raw['quality_missing']=={},'ORIGINAL_SCOPED_QA')
        x=np.asarray(subset['features'],float);need(x.shape==(39,) and np.all(np.isfinite(x)),'FINITE_LEGAL39')
        initial=np.asarray(initial14(subset));ev=original_events(reader,P,{r['id'] for r in rows});events_all[str(P.relative_to(reader.repo))+'/'+group]=ev
        group_index.append(dict(group_evaluation_only=group,case_sha256_evaluation_only=config['case_sha256'],parent_full_hash_evaluation_only=g['parent_full_hash'],missing_tags_evaluation_only=g['missing_tags'],input39_sha256=digest(subset)))
        for row in rows:
            reader.check();ident=row['id'];saved=byaudit[ident]
            identity=identity_by_id[ident]
            need(all(identity[k]==saved[k] for k in ('id','group','trace_path','trace_sha256','source_result_path','source_result_sha256','common_initial14_sha256','TASK_node_count','TASK_duration_s')),'EXACT_E2_SOURCE_ALLOWLIST_ROW')
            original=reader.json(saved['source_result_path'],saved['source_result_sha256'])
            need(original.get('complete') is True and original.get('error') is None and type(original.get('qualified')) is bool,'NO_PARTIAL_OR_UNKNOWN_LABELS')
            need(original['branch']['full_hash']==g['parent_full_hash']==row['parent_evaluation_only']['snapshot_full_hash'],'SAME_ORIGINAL_PARENT')
            need(ev[ident+'|START']['record']['config_sha256']==g['config_sha256'],'START_CONFIG_SHA')
            recipe=next(m for m in menu if m['recipe_sha256']==row['action_recipe_sha256']);need(recipe['action_recipe']==row['action_recipe'] and recipe['action']==original['action'],'FULL_RECIPE_ACTION_IDENTITY')
            binding_path=P/'attempts'/(ident+'_EXECUTION_BINDING.json');binding=reader.json(binding_path);candidate=dict(binding['candidate']);candidate.pop('id',None)
            need(binding['action']==recipe['action'] and candidate==recipe['action_recipe']['resolved_base_candidate'] and binding.get('truth_used') is False,'ORIGINAL_EXECUTION_BINDING')
            measured_path=P/original['metrics_path'];measured=reader.json(measured_path)
            need(measured['id']==ident and measured['J_F_N_s']==original['JF'] and measured['moment_integral_Nm_s']==original['JM'],'ORIGINAL_MEASURED_COST_IDENTITY')
            need(measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS' and measured['native_physical_audit']['pass_'] is True,'ORIGINAL_PHYSICAL_CAUSAL_LEGALITY')
            common=measured['native_physical_audit']['unchanged_evaluator']['physical_task_result']['scorer_v2_common_conditions']
            need(not any(common.get(k) is False for k in HARD),'ORIGINAL_HARD_FALSE')
            need(all(common.get(k) is True for k in HARD),'ORIGINAL_HARD_UNKNOWN')
            line_path=reader.path(measured['execution_lineage_path']);need(line_path.is_relative_to(P),'LINEAGE_PACKAGE_IDENTITY');line=reader.json(line_path)
            need(line['id']==ident and line['status']=='PASS' and line['ownership_error_count']==0,'ORIGINAL_RECEIPT_LINEAGE')
            positive=[r for r in line['rows'] if r.get('selected_plan_activated') is True and r.get('actual_native_steps',0)>0]
            need(positive,'ORIGINAL_ACTIVATION_POSITIVE_RECEIPT_REQUIRED')
            trace=reader.path(saved['trace_path']);reader.hash(trace,saved['trace_sha256']);reader.traces+=1
            with np.load(trace,allow_pickle=False) as archive:z={k:archive[k] for k in FIELDS}
            ids=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ids];y=np.c_[z['estimated_human_state_rad_rad_s'][ids],z['reference_q_rad'][ids],z['reference_dq_rad_s'][ids],z['physical_cuff_force_world_n'][ids],z['physical_cuff_moment_world_nm'][ids]]
            need(len(ids)==3807 and np.all(np.isfinite(y)) and np.max(np.abs(np.diff(t)-.005))<2e-9,'FINITE_COMPLETE_5MS_LABEL_GRID')
            need(float(t[0])==float(raw['physical_s']) and np.array_equal(y[0],initial) and digest(y[0].tolist())==saved['common_initial14_sha256'],'FIRST_TASK_EXACT_COMMON_PREACTION_OUT0')
            need(bool(z['terminal_boundary_node'][ids[-1]]),'ORIGINAL_TERMINAL_BOUNDARY')
            interval=np.c_[np.linalg.norm(y[:-1,8:11],axis=1),np.linalg.norm(y[:-1,11:14],axis=1)]*np.diff(t)[:,None]
            cumulative=np.vstack([np.zeros((1,2)),np.cumsum(interval,axis=0)])
            need(np.max(np.abs(cumulative[-1]-[original['JF'],original['JM']]))<1e-6,'UNCHANGED_ORIGINAL_LEFT_COST_CLOSURE')
            offsets=[int(round(h/.005)) for h in HORIZONS]
            need(all(abs(float(t[k]-t[0])-h)<2e-8 for k,h in zip(offsets,HORIZONS)),'EXACT_HORIZON_NODE_NO_INTERPOLATION')
            old_offsets=[100,200,400,800,1600,2400,3200]
            old_target=digest({'endpoint14':y[old_offsets].tolist(),'window_JF_JM':cumulative[old_offsets].tolist(),'dense14_sha256':hashlib.sha256(y[:3201].astype('<f8').tobytes()).hexdigest(),'dense_cost_sha256':hashlib.sha256(cumulative[:3201].astype('<f8').tobytes()).hexdigest()})
            old_row=f1_by_id[ident]
            need(old_target==old_row['evaluation_only']['logical_target_sha256'] and old_row['input']['features']==x.tolist() and old_row['input']['full_recipe_sha256']==recipe['recipe_sha256'] and old_row['input']['recipe_index']==menu.index(recipe),'F1_PREFIX_AND_INPUT_BYTES_PRESERVED')
            need(abs(float(t[-1]-t[0])-19.03)<2e-8 and ids[-1]==ids[3806],'EXACT_FULLTASK_19_03_TERMINAL_NOT_INTERPOLATED')
            target=digest({'endpoint14':y[offsets].tolist(),'window_JF_JM':cumulative[offsets].tolist(),'dense14_sha256':hashlib.sha256(y.astype('<f8').tobytes()).hexdigest(),'dense_cost_sha256':hashlib.sha256(cumulative.astype('<f8').tobytes()).hexdigest()})
            records.append(dict(id=ident,input=dict(feature_names=FEATURE_NAMES,features=x.tolist(),recipe_index=menu.index(recipe),full_recipe_sha256=recipe['recipe_sha256']),
                evaluation_only=dict(group=group,case_sha256=config['case_sha256'],parent_full_hash=g['parent_full_hash'],tag=recipe['tag'],original_complete=True,original_qualified=original['qualified'],original_motion_failed_requirements=original['motion_vs_B']['failed_requirements'],full_JF_JM=[original['JF'],original['JM']],
                    positive_activated_decisions=len(positive),actual_nonzero_native_steps=line.get('actual_nonzero_native_steps'),requested_recipe_not_every_native_owner=True,trace_sha256=saved['trace_sha256'],logical_target_sha256=target,execution_binding_sha256=reader.files[str(binding_path.relative_to(reader.repo))],original_lineage_sha256=reader.files[str(line_path.relative_to(reader.repo))])))
            dense.append(y);costs.append(cumulative);clocks.append(t-t[0]);endpoints.append(y[offsets]);windows.append(cumulative[offsets]);reader.hash(trace,saved['trace_sha256'])
    need(len(records)==48 and len(group_index)==10 and len({g['case_sha256_evaluation_only'] for g in group_index})==10,'FINAL48_TEN_CONTEXT_CASE_IDENTITY')
    need(sum(r['evaluation_only']['original_qualified'] for r in records)==31,'ORIGINAL_QUALIFICATION_COUNTS_NOT_CHANGED')
    need([r['id'] for r in records]==[r['id'] for r in f1['rows']] and menu==f1['menu'],'ORIGINAL_F1_ROW_ORDER_AND_MENU_UNCHANGED')
    reader.stable()
    for key,ev in events_all.items():
        package_name,group=key.split('/',1);P=reader.repo/package_name
        need(original_events(reader,P,{r['record']['id'] for r in ev.values()})==ev,'ORIGINAL_EVENT_CHANGED_DURING_BUILD')
    index=dict(schema='v8.E.common_out0_fulltask_e2_index.v1',feature_names=FEATURE_NAMES,menu=menu,horizons_s=list(HORIZONS),rows=records,groups_evaluation_only=group_index,
        targets_file='TARGETS_CAUSAL_ONLY.npz',row_order='exact audit group order then exact frozen old48 row order within group',future_targets_are_not_actor_inputs=True,clinical_population_IID=False,new_physics=0)
    write_new(out/'INDEX.json',index)
    with (out/'TARGETS_CAUSAL_ONLY.npz').open('xb') as f:
        np.savez_compressed(f,endpoint14=np.asarray(endpoints),window_JF_JM=np.asarray(windows),dense14=np.asarray(dense),dense_cost_JF_JM=np.asarray(costs),dense_actual_elapsed_s=np.asarray(clocks),dense_public_query_s=np.arange(3807,dtype=float)*.005,horizons_s=np.asarray(HORIZONS));f.flush();os.fsync(f.fileno())
    reader.stable();reader.check()
    dataset_manifest=dict(schema='v8.E.common_out0_fulltask_e2_dataset_manifest.v1',status='BUILT_ORIGINAL_SOURCE_BOUND_NO_FIT',actual_rows=48,parent_contexts=10,distinct_case_SHA=10,original_qualified=31,complete_original_unqualified=17,
        files_sha256={name:sha(out/name) for name in ['INDEX.json','TARGETS_CAUSAL_ONLY.npz']},index_canonical_sha256=digest(index),source_files_sha256=reader.files,original_event_records_and_hash_scopes=events_all,
        build_contract_sha256=sha(root/BUILD_CONTRACT_REL),build_source_manifest_sha256=approval['source_manifest_sha256'],approval_sha256=approval['_actual_approval_sha256'],availability_audit_sha256=sha(root/AUDIT_REL),
        trace_fields_read_allowlist=list(FIELDS),read_raw_gzip=False,evaluation_truth_arrays_read=False,future_target_values_not_inputs=True,missing_two_action_labels_not_imputed=True,
        original_cost_rule='unchanged 5ms TASK left quadrature',F1_prefix_label_SHA_verified_rows=48,full_TASK_boundary_nodes=3807,terminal_query_s=19.03,matched_training_domains=contract['matched_training_domains'],dense_labels_training_authorized=False,dataset_build_count=1,model_initializations=0,model_calls=0,fit=0,physics=0)
    write_new(out/'DATASET_MANIFEST.json',dataset_manifest)
    return dict(status='PASS_FULLTASK_E2_ONE_SHOT_DATASET_BUILD_NO_FIT',output_directory=OUT_REL,actual_rows=48,parent_contexts=10,distinct_case_SHA=10,
        dataset_files_sha256=dataset_manifest['files_sha256'],dataset_manifest_sha256=sha(out/'DATASET_MANIFEST.json'),json_reads=reader.json_reads,traces_read=reader.traces,model_initializations=0,model_forward=0,fit=0,physics=0,sealed_reads=0)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',required=True);parser.add_argument('--approval',required=True);parser.add_argument('--approval-sha256',required=True)
    args=parser.parse_args();started=time.monotonic();cpu=time.process_time();root=Path(args.package).resolve()
    need(root==PACKAGE.resolve(),'ONLY_UNIQUE_V8_PACKAGE');ap=(root/args.approval).resolve();need(ap.is_relative_to(root),'APPROVAL_PATH')
    need(sha(ap)==args.approval_sha256,'EXACT_MAIN_APPROVAL_BYTES');approval=load(ap)
    need(approval.get('schema')=='v8.E.common_out0_fulltask_e2_build_approval.v1' and approval.get('status')=='APPROVED_BY_MAIN_AGENT' and approval.get('operation')=='READ_ONLY_FULLTASK_DATASET_BUILD_ONLY' and bool(approval.get('main_approval_id')),'EXPLICIT_ONE_SHOT_BUILD_APPROVAL_REQUIRED')
    need(approval.get('activation_id')==ACTIVATION and approval.get('global_deadline_unix')==STOP and approval.get('output_directory')==OUT_REL,'ORIGINAL_CLOCK_AND_OUTPUT_BINDING')
    need(approval.get('resources')==dict(CPU_threads=1,wall_s=120,memory_bytes=1073741824,model_init=0,model_forward=0,fit=0,physics=0,auto_retry=False),'EXACT_BUILD_RESOURCE_APPROVAL')
    need(approval.get('source_manifest_path')==MANIFEST_REL and sha(root/MANIFEST_REL)==approval['source_manifest_sha256'],'EXACT_BUILD_SOURCE_MANIFEST')
    need(approval.get('build_contract_path')==BUILD_CONTRACT_REL and sha(root/BUILD_CONTRACT_REL)==approval['build_contract_sha256'],'EXACT_BUILD_CONTRACT')
    need(time.time()<STOP,'GLOBAL_DEADLINE_EXPIRED');a=load(root/'ACTIVATION.json');need(a['activation_id']==ACTIVATION and a['hard_stop_unix']==STOP,'UNIQUE_ACTIVATION')
    source=load(root/MANIFEST_REL)
    for rel,expected in source['files_sha256'].items():need(sha(root/rel)==expected,'SOURCE_CHANGED_BEFORE_BUILD:'+rel)
    out=root/OUT_REL;need(not out.exists(),'ONE_SHOT_EXISTING_OUTPUT_NO_RETRY');out.mkdir(parents=True)
    approval['_actual_approval_sha256']=args.approval_sha256
    deadline=started+120.;reader=Reader(root,deadline)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(120,121))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ONE_SHOT_BUILD_DEADLINE')));signal.setitimer(signal.ITIMER_REAL,min(deadline-time.monotonic(),STOP-time.time()))
    write_new(out/'BUILD_START.json',dict(status='START_ONE_SHOT_NO_RETRY',pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),approval_sha256=args.approval_sha256,source_manifest_sha256=approval['source_manifest_sha256'],actual_python=str(Path(sys.executable).resolve()),actual_python_binary_sha256=sha(Path(sys.executable).resolve()),python_version=platform.python_version(),created_unix=time.time(),original_global_stop=STOP))
    try:
        for rel,expected in source['files_sha256'].items():reader.hash(root/rel,expected)
        reader.hash(root/MANIFEST_REL,approval['source_manifest_sha256'])
        reader.hash(ap,args.approval_sha256)
        import numpy as np
        answer=perform(reader,out,approval,source,np);answer.update(wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,numpy_version=np.__version__,numpy_module=str(Path(np.__file__).resolve()))
        write_new(out/'BUILD_EXECUTION_RECEIPT.json',answer);print(json.dumps(answer,allow_nan=False))
    except BaseException as exc:
        write_new(out/'BUILD_FAILED.json',dict(status='FAILED_PRESERVE_NO_AUTORETRY',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,model=0,fit=0,physics=0,source_files_read_sha256=reader.files));raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

if __name__=='__main__':main()
