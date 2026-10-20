"""Serial patient-specific cold commissioning and frozen full-live-state forks.

Orchestration only: all controller methods are inherited from frozen campaign_v2.
Failures remain independent arms; no control/safety assertion is disabled.
"""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,hashlib,copy,inspect
P=Path(__file__).resolve().parent
GROUP=sys.argv[1]
os.environ.update(STUDY_GROUP=GROUP,STUDY_MODE='cross_patient',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True
sys.path[:0]=[str(P),str(P/'control'),str(P/'code')]
import campaign_v2 as frozen
import study_common as sc,matched_harness as mh
import cross_analysis as ca
import numpy as np
from patient_models import digest as case_digest
ca.configure(P)
PLAN=json.loads((P/'RUN_PLAN.json').read_text())
CONFIG=json.loads((P/(GROUP+'_PLAN.json')).read_text())
PATIENT=CONFIG['patient']
CASE=json.loads((P/PATIENT['case_path']).read_text())
ORIGINAL_CASE,OPTIONS=sc.load_case_options()
assert CASE['task']==ORIGINAL_CASE['task']
sc.load_case_options=lambda:(copy.deepcopy(CASE),copy.deepcopy(OPTIONS))
def put(n,x):mh.put(P/n,sc.clean(x))
_original_initialize=sc.rt._initialize_loaded_runtime
def audited_initialize(*args,**kwargs):
    from traction_mpc_stage5.high_rom_v1 import deployable_prior as high_rom_deployable_prior
    static=json.loads((P/'patients'/PATIENT['patient_id']/'static/MODEL_STATIC_AUDIT.json').read_text())
    assert sc.clean(kwargs['physical_human'])==static['human_dataclass'],'PLANT_MODEL_IDENTITY_MISMATCH'
    assert sc.clean(kwargs['control_human'])==sc.clean(high_rom_deployable_prior()),'P0_CONTROL_PRIOR_CHANGED'
    runtime=_original_initialize(*args,**kwargs)
    put('audit/'+GROUP+'_RUNTIME_MODEL_IDENTITY.json',dict(status='PASS',physical_human=sc.clean(runtime['plant'].human),control_prior=sc.clean(kwargs['control_human']),control_prior_source='FROZEN_HIGH_ROM_DEPLOYABLE_PRIOR_NOT_PATIENT_TRUTH',case_sha256=PATIENT['case_sha256'],xml_sha256=static['xml_sha256'],time_s=float(runtime['plant'].data.time),physics_step_count=0,scope='generation-side audit; fields never supplied to controller'))
    return runtime
sc.rt._initialize_loaded_runtime=audited_initialize
# The historical scorer hardcoded the nominal case filename. Bind only its
# provenance path to the actual immutable patient case; all score logic stays.
import mode_metadata as mm
import qualify as original_qualify
import final_qualification as original_final
_audit_source=inspect.getsource(original_qualify.physical_audit)
_case_text="case_path=S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'"
assert _audit_source.count(_case_text)==1
_audit_revised=_audit_source.replace(_case_text,'case_path=PATIENT_CASE_PATH').replace('str(case_path.relative_to(R))','str(case_path)').replace("execution_mode='SCIENTIFIC_SIMULATION'","execution_mode=env.summary['execution_mode']")
_audit_namespace=dict(original_qualify.__dict__,PATIENT_CASE_PATH=P/PATIENT['case_path'])
exec(compile(_audit_revised,'<unchanged evaluator with actual patient provenance path>','exec'),_audit_namespace)
_patient_audit=_audit_namespace['physical_audit']
_original_mode_install=mm.install
def install_patient_evaluation_metadata():
    _original_mode_install()
    original_qualify.physical_audit=original_final.physical_audit=_patient_audit
    mm.INSTALLED_AUDIT=_patient_audit
    put('audit/'+GROUP+'_PATIENT_EVALUATOR_BINDING.json',dict(original_function_sha256=hashlib.sha256(_audit_source.encode()).hexdigest(),adapted_function_sha256=hashlib.sha256(_audit_revised.encode()).hexdigest(),changes=['actual patient case_path','absolute evaluation input path','original execution-mode metadata correction retained'],case_path=str(P/PATIENT['case_path']),case_sha256=PATIENT['case_sha256'],controller_changed=False,scoring_formula_or_threshold_changed=False))
mm.install=install_patient_evaluation_metadata
def dispatch(ident,**extra):
    now=time.time();records=mh.records()
    assert sum(x['event']=='START' for x in records)<PLAN['physics_budget'],'START_CAP'
    assert now<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'FINAL_45_MIN_RESERVE'
    assert not (P/'PHYSICS_STOP.json').exists(),'STUDY_STOPPED'
    assert not any(x['event']=='START' and x['id']==ident for x in records),'NO_DUPLICATE_ATTEMPT'
    assert sc.sha(P/PATIENT['case_path'])==PATIENT['case_sha256'],'PATIENT_CASE_CHANGED'
    static_dir=P/'patients'/PATIENT['patient_id']/'static'
    static=json.loads((static_dir/'MODEL_STATIC_AUDIT.json').read_text())
    assert static['case_sha256']==case_digest(CASE),'STALE_STATIC_CASE'
    assert sc.sha(static_dir/'model.xml')==static['xml_sha256'],'STATIC_XML_CHANGED'
    manifest=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text())
    for rel,h in manifest['files'].items():assert sc.sha(P/rel)==h,'SOURCE_CHANGED:'+rel
    mh.event('START',ident,patient_id=PATIENT['patient_id'],case_sha256=PATIENT['case_sha256'],source_sha256=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),plan_sha256=sc.sha(P/(GROUP+'_PLAN.json')),**extra)
    put('STATE.json',dict(phase='P0_SERIAL_PHYSICS',last=ident,patient=PATIENT['patient_id'],physics_starts=sum(x['event']=='START' for x in records)+1,owned_pids=[os.getpid()]))
mh.dispatch=dispatch

class PatientPair(frozen.Campaign):
    def __init__(self,cond):
        super().__init__(cond);self.online_records=[];self.arm_errors=[]
    def control(self,b):
        # Log only explicitly causal signals already used by frozen controller.
        obs=np.asarray(b['observation'].as_array(),float)
        ref=np.asarray(b['arguments']['current_reference_state'],float)
        measured=b['interface'];req=b['request']
        self.online_records.append(dict(phase=b['task_state'].phase.value,elapsed_s=float(b['task_state'].phase_elapsed_s),physical_s=float(b['physical_now']),estimated_q_dq=obs[:4].tolist(),reference_q_dq=ref[:4].tolist(),tracking_q_dq=(obs[:4]-ref[:4]).tolist(),force_world_N=np.asarray(measured.measured_force_world_n).tolist(),moment_world_Nm=np.asarray(measured.measured_moment_world_nm).tolist(),source_sample_time_s=float(req.source_sample_time_s),source_age_s=float(b['physical_now']-req.source_sample_time_s),request_id=req.request_id,slot=dict(self.count),action=None if self.current is None else self.current['id'],truth_used=False))
        return super().control(b)
    def fork(self,b,tag,table=None):
        try:
            child=super().fork(b,tag,table)
        except AssertionError as error:
            # These three checks are historical orchestration stop policies,
            # downstream of child completion. No actuator/native safety changes.
            message=str(error)
            allowed=(message.startswith('CHILD_FAILED:') or message.startswith('NATIVE_PHYSICAL_FAILURE:'))
            if not allowed:raise
            assert self.child is None and self.active_owned_child_pid is None
            assert self.parent_checks and self.parent_checks[-1]['unchanged'],'PAIR_PARENT_CHANGED'
            self.arm_errors.append(dict(arm=tag,error=message))
            put('audit/'+GROUP+'_ARM_FAILURES.json',self.arm_errors)
            return False
        if child:
            self.branch_start.update(patient_id=PATIENT['patient_id'],case_sha256=PATIENT['case_sha256'],model_xml_sha256=json.loads((P/'patients'/PATIENT['patient_id']/'static/MODEL_STATIC_AUDIT.json').read_text())['xml_sha256'])
            self.online_records=[]
        return child
    def finish(self,env,metric):
        super().finish(env,metric)
        put('learning/'+metric['name']+'_STATE_ACTION.json',dict(patient_id=PATIENT['patient_id'],split=PATIENT['future_learning_split'],causal_rows=self.online_records,policy=self.current,truth_firewall='Only causal observation/reference/measured wrench/request metadata; physical parameter truth separate in patient manifest'))
    def decision_boundary(self,b):
        if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=CONFIG['fork_after_prefix']:
            self.fork_done=True
            signal.alarm(max(1,min(3*PLAN['physical_timeout_s'],int(PLAN['physics_hard_stop_unix']-time.time()))))
            put('audit/'+GROUP+'_FORK_CONTEXT.json',dict(patient_id=PATIENT['patient_id'],physical_s=float(b['physical_now']),task_s=float(b['physical_now']-b['task_start_time']),count=self.count.copy(),manifest=self.manifest(b),cold_commissioning_reached=True,patient_case_sha256=PATIENT['case_sha256']))
            for candidate in CONFIG['arms']:
                if self.fork(b,candidate['id'],np.zeros((2,5,3))):
                    self.current=candidate;self.references={};self.sample_rows=[];self.terminal_intent=None
                    signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))))
                    return self.control(b)
                ident=GROUP+'_'+candidate['id']
                row=ca.evaluate_run(ident,arm=candidate['id'],case=CASE,candidate=candidate)
                self.results.append(row)
                put(GROUP+'_RESULTS.json',dict(patient_id=PATIENT['patient_id'],condition=self.condition,rows=self.results,arm_errors=self.arm_errors))
                print('ARM_END',ident,json.dumps(dict(task=row['axes']['task'],absolute_safety=row['axes']['absolute_safety'],causal=row['axes']['causal_execution'],J_F_N_s=row.get('J_F_N_s'),complete_task=row.get('complete_task'))),flush=True)
            paired=ca.compare_pair(PATIENT['patient_id'],self.results[0],self.results[1])
            put(GROUP+'_COMPARISON.json',paired)
            hashes={r['id']:json.loads((P/'output'/(r['id']+'_DATA.json')).read_text())['branch_start']['full_hash'] for r in self.results if (P/'output'/(r['id']+'_DATA.json')).exists()}
            put(GROUP+'_PAIR_GATE.json',dict(status='PASS' if len(hashes)==2 and len(set(hashes.values()))==1 and all(x['unchanged'] for x in self.parent_checks) else 'INCOMPLETE_OR_FAIL',hashes=hashes,parent_checks=self.parent_checks,patient_case_sha256=PATIENT['case_sha256'],patient_id=PATIENT['patient_id']))
        self.control(b)

def main():
    static=json.loads((P/'patients'/PATIENT['patient_id']/'static/MODEL_STATIC_AUDIT.json').read_text())
    assert static['model_static_valid'],'STATIC_MODEL_NOT_ADMISSIBLE'
    lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    it=PatientPair(CONFIG['condition']);ident=GROUP+'_parent';started=time.time()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_PHYSICS_TIMEOUT')))
    signal.alarm(max(1,min(PLAN['physical_timeout_s'],int(PLAN['physics_hard_stop_unix']-time.time()))))
    dispatch(ident,kind='OWN_PATIENT_COLD_INITIALIZATION_COMMISSIONING_PARENT',condition=CONFIG['condition'])
    random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
    try:
        metric=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
        if it.child is not None:os._exit(0)
        mh.event('END',ident,returncode=0,joined=True,task_valid=metric['task_valid'],wall_seconds=time.time()-started,native_physics_steps=metric['native_physics_steps'])
        parent=ca.evaluate_run(ident,arm='B',case=CASE,candidate=CONFIG['arms'][0])
        put(GROUP+'_PARENT_RESULT.json',parent)
        if (P/'source/results'/(GROUP+'_B')/'trace.npz').exists():
            gate=frozen.bc.compare_raw(P/'source/results'/ident,P/'source/results'/(GROUP+'_B'))
            put(GROUP+'_PARENT_GATE.json',gate)
        put(GROUP+'_DONE.json',dict(status='EXECUTED_WITH_REPORTED_QUALIFICATIONS',unix=time.time(),all_children_joined=True,rows=len(it.results),cold_commissioning_reached=it.fork_done))
    except BaseException as error:
        actual=ident if it.child is None else it.child['label']+'_'+it.child['kind']
        put('reports/'+actual+'_ERROR.json',dict(error=str(error),traceback=traceback.format_exc(),unix=time.time()))
        put('learning/'+actual+'_PARTIAL_STATE_ACTION.json',dict(causal_rows=it.online_records,policy=it.current,patient_id=PATIENT['patient_id'],partial=True))
        if it.child is not None:os._exit(1)
        if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(error),wall_seconds=time.time()-started)
        try:put(GROUP+'_PARENT_RESULT.json',ca.evaluate_run(ident,arm='B',case=CASE,candidate=CONFIG['arms'][0]))
        except Exception as audit_error:put(GROUP+'_PARENT_AUDIT_ERROR.json',dict(error=str(audit_error),traceback=traceback.format_exc()))
        put(GROUP+'_DONE.json',dict(status='FAILED_PRESERVED',error=str(error),unix=time.time(),all_children_joined=getattr(it,'active_owned_child_pid',None) is None,cold_commissioning_reached=it.fork_done,rows=len(it.results)))
        print('PATIENT_FAILURE',GROUP,str(error),flush=True)
        # Continue next preregistered patient only from an independent cold process.
        raise
    finally:
        if it.child is None:
            signal.alarm(0);put(GROUP+'_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
