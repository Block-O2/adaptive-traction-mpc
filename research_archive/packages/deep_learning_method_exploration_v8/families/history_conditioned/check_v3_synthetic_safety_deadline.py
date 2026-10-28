"""Approved <=60s SYNTHETIC_ONLY V3 safety/deadline fixture; no numeric fit.

No worker/runtime import, NumPy, MuJoCo, real fork, real data or physics.
The real V3 decision method is AST-extracted into mocks for stop attribution.
"""
from pathlib import Path
import ast,hashlib,json,sys,time,types
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parent
sys.path.insert(0,str(F))
from failed_child_safety_v3 import inspect_closed_failed_child,HARD_FIELDS
from owner_deadline_v3 import make_owner_deadline,arm_owner_deadline


def main():
    began=time.monotonic();cpu=time.process_time();checks=[];root=F/'audit/SYNTHETIC_ONLY_V3_SAFETY_DEADLINE'
    output=F/'CONTINUOUS_V3_SYNTHETIC_SAFETY_DEADLINE_FIXTURE.json'
    if root.exists() or output.exists():raise RuntimeError('DO_NOT_OVERWRITE_SYNTHETIC_RECEIPT')
    root.mkdir(parents=True)
    def put(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
    def check(name,value,details=None):checks.append(dict(name=name,pass_=bool(value),details=details))
    def case(name,*,data=None,partial=None,result=None,delta=None,joined=True):
        p=root/name;ident='SYN_'+name
        put(p/'runtime/ATTEMPTS.jsonl',{})
        (p/'runtime/ATTEMPTS.jsonl').write_text('\n'.join(json.dumps(r) for r in [dict(event='START',id=ident),dict(event='END',id=ident,joined=joined,returncode=1)])+'\n')
        for relative,value in [(f'runtime/output/{ident}_DATA.json',data),(f'runtime/output/{ident}_PARTIAL_COMPUTE.json',partial),
            (f'attempts/{ident}_RESULT.json',result),(f'audit/persistent/{ident}_PERSISTENT_DELTA_ACCOUNTING.json',delta)]:
            if value is not None:put(p/relative,value)
        return p,ident
    def metric(checks,steps=493,**extra):
        return dict(metric=dict(actual_new_native_physics_steps=steps,J_F=12.5,task_valid=False,
            physical_audit=dict(pass_=False,unchanged_evaluator=dict(physical_task_result=dict(scorer_v2_common_conditions=checks,**extra)))))
    alltrue={k:True for k in HARD_FIELDS}
    false=dict(alltrue,force=False)
    p,ident=case('DATA_HARD_FALSE',data=metric(false))
    data_false=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('missing_RESULT_DATA_explicit_hard_false_stops',data_false['status']=='HARD_FALSE_STOP_STAGE' and data_false['explicit_hard_false']==['force'])
    check('DATA_partial_cost_preserved_unranked',data_false['actual_new_native_steps']==493 and data_false['partial_never_ranked'])
    p,ident=case('PARTIAL_HARD_FALSE',partial=dict(actual_new_native_physics_steps=504,physical_audit=dict(unchanged_evaluator=dict(raw_scorer_v2=dict(conditions=dict(alltrue,moment=False))))))
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('PARTIAL_original_scorer_hard_false_stops',out['status']=='HARD_FALSE_STOP_STAGE' and out['actual_new_native_steps']==504 and 'moment' in out['explicit_hard_false'])
    p,ident=case('UNKNOWN_PARTIAL',partial=dict(actual_new_native_physics_steps=129))
    unknown=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('missing_physical_audit_is_UNKNOWN_not_safe',unknown['status']=='UNKNOWN_STOP_STAGE' and len(unknown['unknown_hard_fields'])==11 and unknown['actual_new_native_steps']==129)
    complete=dict(id='SYN_MOTION_ONLY',action={'family':'H150'},complete=True,qualified=False,actual_new_native_steps=200,
        original_physical_audit=dict(pass_=True,unchanged_evaluator=dict(physical_task_result=dict(scorer_v2_common_conditions=alltrue))),
        motion_vs_B=dict(acceptance_pass=False,failed_requirements=['jerk_deg_s3/rms']))
    p,ident=case('MOTION_ONLY',result=complete)
    motion=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:post_task_software',joined=True)
    check('motion_failure_not_blanket_hard_stop',motion['status']=='HARD_FIELDS_CONFIRMED_TRUE_ONLY' and not motion['explicit_hard_false'])
    p,ident=case('TASK_COMPLETION_ONLY',data=metric(dict(alltrue,true_return=False)))
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:task_incomplete',joined=True)
    check('completion_failure_not_relabelled_hard_false',out['status']=='HARD_FIELDS_CONFIRMED_TRUE_ONLY' and out['partial_never_ranked'])
    p,ident=case('CONFLICT_FALSE_WINS',data=metric(alltrue),partial=metric(dict(alltrue,torque=False),steps=400),delta=dict(actual_new_native_steps=503))
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('any_original_false_wins_and_cost_conflict_retained',out['status']=='HARD_FALSE_STOP_STAGE' and out['actual_new_native_steps']==503 and out['count_source']=='PERSISTENT_DELTA' and out['cost_counter_disagreement'])
    p,ident=case('FINITE_NATIVE_FALSE',data=metric(alltrue,finite_native=False))
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('explicit_nonfinite_physical_state_stops',out['status']=='HARD_FALSE_STOP_STAGE' and out['explicit_physical_finiteness_false'])
    p,ident=case('NOT_JOINED',data=metric(false),joined=False)
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=False)
    check('unclosed_failure_never_reads_raw_documents',out['status']=='UNKNOWN_STOP_STAGE' and out['raw_documents_read'] is False)
    p,ident=case('MALFORMED_SOURCE',partial=dict(actual_new_native_physics_steps=321))
    (p/'runtime/output'/(ident+'_DATA.json')).write_text('{not_closed_json')
    out=inspect_closed_failed_child(p,ident,failure='CHILD_FAILED:1',joined=True)
    check('malformed_closed_source_UNKNOWN_cost_retained',out['status']=='UNKNOWN_STOP_STAGE' and out['actual_new_native_steps']==321 and out['source_read_errors'])

    timers=[];deadline=make_owner_deadline(400,now_monotonic=100)
    first=arm_owner_deadline(deadline,3600,campaign_stop_unix=10000,now_monotonic=100,now_unix=1000,timer_writer=timers.append)
    after=arm_owner_deadline(deadline,3600,campaign_stop_unix=10000,now_monotonic=107,now_unix=1007,timer_writer=timers.append)
    check('attempt_parent_alarm_400_to393_not3600_reset',first==400 and after==393,timers)
    inherited=make_owner_deadline(3600,inherited_deadline=deadline,now_monotonic=107)
    remaining=arm_owner_deadline(inherited,600,campaign_stop_unix=10000,now_monotonic=107,now_unix=1007,timer_writer=timers.append)
    check('nested_T3_inherits_outer_deadline',inherited==deadline and remaining==393)
    early=arm_owner_deadline(deadline,600,campaign_stop_unix=1020,now_monotonic=107,now_unix=1007,timer_writer=timers.append)
    check('earlier_campaign_deadline_not_extended',early==13)
    expired=False
    try:arm_owner_deadline(deadline,600,campaign_stop_unix=10000,now_monotonic=500,now_unix=1000,timer_writer=timers.append)
    except TimeoutError:expired=True
    check('expired_owner_raises_without_minimum_one_second_extension',expired)

    # Reproduce the parent's reported missing RESULT path in the actual V3
    # method, isolated via AST. self.fork is a mock assertion, not os.fork.
    tree=ast.parse((F/'continuous_ilc_worker_v3.py').read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StageStudy')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='decision_boundary')
    stage_results=[]
    for name,checks_value,expected_stop in [('SOURCE_HARD_FALSE',false,True),('SOURCE_UNKNOWN',None,True),('SOURCE_MOTION_ONLY',alltrue,False)]:
        p,ident=case(name,data=metric(checks_value) if checks_value is not None else None,partial=dict(actual_new_native_physics_steps=493) if checks_value is None else None)
        stage='SYN';tag=name;actual=stage+'_'+tag
        # Rebind synthetic original filenames to the stage's exact actual ID.
        for path in list(p.rglob(ident+'*')):path.rename(path.with_name(path.name.replace(ident,actual,1)))
        (p/'runtime/ATTEMPTS.jsonl').write_text('\n'.join(json.dumps(r) for r in [dict(event='START',id=actual),dict(event='END',id=actual,joined=True,returncode=1)])+'\n')
        emitted={};controls=[];forks=[];clock=[100.];armed=[]
        fake=types.SimpleNamespace(stage=2,child=None,count={'OUTBOUND':0},fork_done=False,bo_considered=False,stage_prefix=stage,
            arms=[dict(tag=tag,action={'family':'H150','legacy':[0.,0.]})],results=[],parent_checks=[{'unchanged':True}],active_owned_child_pid=None)
        def writer(path,row):emitted[path]=row;put(p/path,row)
        def fakefork(*a):forks.append('SYNTHETIC_CALLBACK');clock[0]+=7.;raise AssertionError('CHILD_FAILED:SYNTHETIC_CLOSED')
        fake.fork=fakefork;fake.control=lambda b:controls.append('CONTROL_WOULD_ADVANCE')
        fake.arm_owner_budget=lambda maximum:arm_owner_deadline(500.,maximum,campaign_stop_unix=10000,now_monotonic=clock[0],now_unix=1000+clock[0]-100,timer_writer=armed.append)
        fake._consider_bo_once=lambda b:(_ for _ in ()).throw(AssertionError('NO_FIT_ALLOWED_IN_FIXTURE'))
        base=types.SimpleNamespace(C={'nested_owner_timeout_s':3600},PLAN={'physical_timeout_s':600},put=writer,append=lambda *a:None,sc=types.SimpleNamespace(digest=lambda x:json.dumps(x,sort_keys=True)))
        ns=dict(P=p,base=base,json=json,inspect_closed_failed_child=inspect_closed_failed_child,np=types.SimpleNamespace(zeros=lambda shape:'SYNTHETIC_TABLE'))
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<SYNTHETIC_ONLY V3 failure branch>','exec'),ns)
        error=None
        try:ns['decision_boundary'](fake,{'task_state':types.SimpleNamespace(phase=types.SimpleNamespace(value='OUTBOUND'))})
        except RuntimeError as exc:error=str(exc)
        audit=emitted['audit/persistent/'+actual+'_CLOSED_FAILED_CHILD_SAFETY_V3.json']
        stage_results.append(dict(case=name,error=error,controls=len(controls),fork_callbacks=len(forks),native_cost=audit['actual_new_native_steps'],timers=armed))
        check('actual_V3_method_stop_policy_'+name,(error is not None)==expected_stop and len(forks)==1 and len(controls)==(0 if expected_stop else 1),stage_results[-1])
        check('actual_V3_method_preserves_original_failed_cost_'+name,audit['actual_new_native_steps']==493)
        if not expected_stop:check('actual_V3_method_parent_alarm_still393',armed==[400.,393.],armed)
    elapsed=time.monotonic()-began;used=time.process_time()-cpu
    check('approved_singleCPU_under60s',elapsed<60. and used<60.)
    result=dict(status='PASS' if all(c['pass_'] for c in checks) else 'FAIL',dataset_class='SYNTHETIC_ONLY',checks=checks,
        synthetic_json_cases=13,synthetic_AST_stage_cases=3,synthetic_fork_callbacks=3,synthetic_model_solves=0,
        real_fit=0,real_data_read=False,real_fork=0,real_physics_steps=0,wall_s=elapsed,cpu_s=used,
        previous_V2_math_hook_fixture_preserved='C2B_V2_SYNTHETIC_ONLY_FIXTURE.json',
        source_sha256={n:hashlib.sha256((F/n).read_bytes()).hexdigest() for n in ['continuous_ilc_worker_v3.py','failed_child_safety_v3.py','owner_deadline_v3.py',Path(__file__).name]})
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'output':str(output),'status':result['status'],'checks':len(checks),'failed':[c['name'] for c in checks if not c['pass_']],
        'real_fit':0,'physics':0,'wall_s':elapsed,'cpu_s':used}))


if __name__=='__main__':main()
