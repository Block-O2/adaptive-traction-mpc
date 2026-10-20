"""Serial, counted live-state physical exploration and frozen validation."""
import sys, os, json, time, copy, random, signal, traceback, fcntl
from pathlib import Path
import runner as base
from study_common import *
from rich_planner import RichFreePlanner
from scipy.optimize import minimize

base.FreePlanner=RichFreePlanner
S=STUDY; P=json.loads((S/'RUN_PLAN.json').read_text()); MODE=sys.argv[1] if len(sys.argv)>1 else 'development'
base.MODE=MODE; base.P=P
base.SCALES=np.asarray(P['parameter_scales'])
OLD=Path(P['original_sources'])
prior=json.loads((S/'PRIOR_FROZEN_SELECTION.json').read_text())

def dispatch(ident,**extra):
    now=time.time(); count=sum(r['event']=='START' for r in base.mh.records())
    assert count<(P['search_cap'] if MODE.startswith('development') else P['physics_budget']), 'ATTEMPT_RESERVE'
    assert now<P['dispatch_cutoff_unix']-300, 'PHYSICS_DISPATCH_CUTOFF'
    if MODE.startswith('development'): assert now<P['search_cutoff_unix'], 'SEARCH_CUTOFF'
    assert not any(r['event']=='START' and r['id']==ident for r in base.mh.records()), 'DUPLICATE_ATTEMPT'
    base.resource_sample(); base.mh.event('START',ident,mode=MODE,**extra)
    base.put('PROGRESS.json',dict(unix=now,mode=MODE,id=ident,attempts=count+1))

base.mh.dispatch=dispatch; base.sd.dispatch=dispatch; base.dispatch=dispatch

def pad_candidate(c,tag,stage):
    c=copy.deepcopy(c); c.update(id=tag,stage=stage)
    c['free_parameters']=np.pad(np.asarray(c.get('free_parameters',np.zeros(10))),(0,8)).tolist()
    c['normalized_parameters']=(np.asarray(c['free_parameters'])/base.SCALES).tolist()
    return c

class OvernightInterface(base.FreeInterface):
    def __init__(self,condition):
        super().__init__(condition); self.task_failures=0

    def fork(self,b,tag,table=None):
        result=super().fork(b,tag,table)
        if result:
            seconds=max(1,min(600,int(P['physics_hard_stop_unix']-time.time())))
            signal.alarm(seconds)
        return result

    def eval(self,b,cand,stage='main'):
        try:
            return super().eval(b,cand,stage)
        except RuntimeError as error:
            if str(error)!='COMPLETE_TASK_FAILURE_STOP_NO_PARTIAL_RANKING': raise
            ident=self.condition['name']+'_'+cand['id']
            failure=json.loads((S/'reports'/(ident+'_TASK_FAILURE.json')).read_text())
            assert failure['native_absolute_safety_pass'] and failure['actual_write_ownership']=='PASS'
            self.task_failures+=1
            base.append('FAILED_CANDIDATES.jsonl',dict(id=ident,candidate=cand,stage=stage,task_failure=failure,full_gain='NOT_EVALUABLE',excluded_from_ranking=True))
            if self.task_failures>=3: raise RuntimeError('THREE_SAFE_INCOMPLETE_TASKS_STOP_SEARCH')
            # Optimization penalty is explicit; it is not a physical cost or a ranked J_F.
            template=self.eval_rows[0]['constraints']['components']
            components={key:np.full(np.asarray(value).shape,5.).tolist() for key,value in template.items()}
            return dict(id=ident,candidate=cand,J_F_N_s=self.base['J_F_N_s']*2,comparison=dict(acceptance_pass=False,gain_percent=None),constraints=dict(components=components,worst_ratio=5.),optimizer_penalty_only=True)

    def candidate(self,family,z,tag,stage):
        return self.candidate_for(family,np.asarray(z),tag,stage)

    def freeze(self,reason):
        accepted=[r for r in self.eval_rows if r['comparison']['acceptance_pass']]
        best=min(accepted,key=lambda r:r['J_F_N_s'])
        strong=min(self.eval_rows,key=lambda r:r['J_F_N_s'])
        smooth=min([r for r in accepted if r['comparison']['gain_percent']>=1.] or accepted,
                   key=lambda r:(r['constraints']['worst_ratio'],r['J_F_N_s']))
        base.put('FROZEN_SELECTION.json',dict(unix=time.time(),protocol_sha256=sha(S/'RUN_PLAN.json'),best=best,secondary=smooth,diagnostic=strong,heldout_not_used=True,parameters_frozen=True,reason=reason))

    def development(self,b):
        zeros=np.zeros(18)
        baseline=[('B0_original','B0'),('B0_zero_extension','B0'),('NATIVE_SCALAR_18','NATIVE_SCALAR_18'),('M2_fixed_actions','M2_fixed_actions'),('C2_pair_1_2','C2_pair_1_2')]
        for tag,family in baseline:
            self.cache={}
            if self.eval(b,self.candidate(family,zeros,tag,'REFERENCE'),'baseline') is None: return True
            if tag=='B0_zero_extension':
                gate=base.mh.complete_gate('development_B0_original','development_B0_zero_extension')
                base.put('ZERO_EXTENSION_REPRODUCTION_GATE.json',gate); assert gate['status']=='PASS','ZERO_EQUIVALENCE_FAIL'
        previous=pad_candidate(prior['best']['candidate'],'prior_best_18D','REFERENCE')
        self.cache={}
        if self.eval(b,previous,'baseline') is None: return True
        # Historical archive source comparison must use relocated paths but unchanged arrays.
        mismatches=[]
        for a,z in [(O/'development_B0_original'/'trace.npz',OLD/'source/results'/prior['best']['base_id']/'trace.npz'),
                    (O/'development_prior_best_18D'/'trace.npz',OLD/'source/results'/prior['best']['id']/'trace.npz'),
                    (S/'motion_series/development_prior_best_18D.npz',OLD/'motion_series'/(prior['best']['id']+'.npz'))]:
            with np.load(a) as aa,np.load(z) as zz:
                assert set(aa.files)==set(zz.files)
                for key in aa.files:
                    same=aa[key].shape==zz[key].shape and (np.array_equal(aa[key],zz[key],equal_nan=True) if aa[key].dtype.kind in 'fc' else np.array_equal(aa[key],zz[key]))
                    if not same: mismatches.append(dict(file=str(a),field=key))
        base.put('PRIOR_REPRODUCTION_GATE.json',dict(status='PASS' if not mismatches else 'FAIL',errors=mismatches,scope='exact complete control trace and dense true human motion; native body/contact equivalence covered by B zero full gate and source hashes'))
        assert not mismatches,'PRIOR_REPRODUCTION_FAILED'
        base.put('BASELINE_REPRODUCTION.json',dict(status='PASS',runs=self.eval_rows.copy(),same_complete_parent=True,unchanged_plant=True))
        leader=np.asarray(previous['normalized_parameters'])
        try:
            # New dimensions change the spatial shape and hip/knee velocity schedule, rather than rescaling one old residual.
            for axis in range(10,18):
                for sign in [-1,1]:
                    z=leader.copy();z[axis]=sign*.4
                    if self.eval(b,self.candidate('NATIVE_SCALAR_18',z,f'new_axis_{axis}_{sign:+d}','BROAD'),'broad') is None: return True
            # Three physically different regions: old valid teacher, uncoordinated B, and strong low-force pair.
            self.optimize(b,'NATIVE_SCALAR_18',52,'quality')
            if self.child is not None: return True
            self.optimize(b,'B0',24,'alternate')
            if self.child is not None: return True
            self.optimize(b,'C2_pair_1_2',28,'repair')
            if self.child is not None: return True
        except (TimeoutError,StopIteration) as error:
            base.append('SEARCH_STOP_REASONS.jsonl',dict(unix=time.time(),reason=str(error)))
        self.freeze('registered_search_complete_or_time_limit')
        return False

    def optimize(self,b,family,budget,stage):
        candidates=[r for r in self.eval_rows if r['candidate'].get('seed_family')==family]
        leader=min(candidates,key=lambda r:(not r['comparison']['acceptance_pass'],r['J_F_N_s'] if r['comparison']['acceptance_pass'] else r['constraints']['worst_ratio']))
        z0=np.asarray(leader['candidate']['normalized_parameters']); start=self.counter; cache={}
        class BranchStarted(Exception): pass
        def evaluate(z):
            if time.time()>P['search_cutoff_unix']-600: raise TimeoutError('SEARCH_CLOSEOUT_RESERVE')
            key=np.asarray(z,dtype=float).tobytes()
            if key not in cache:
                if np.any(np.abs(z)>1.+1e-12):
                    template=self.eval_rows[0]['constraints']['components']
                    violation=float(np.max(np.abs(z))-1.)
                    components={name:np.full(np.asarray(value).shape,1.+violation).tolist() for name,value in template.items()}
                    cache[key]=dict(J_F_N_s=self.base['J_F_N_s']*(2.+violation),constraints=dict(components=components),optimizer_penalty_only=True)
                    base.append('MATHEMATICAL_REJECTIONS.jsonl',dict(unix=time.time(),stage=stage,z=z,reason='FROZEN_NORMALIZED_BOUNDS',physical_attempt=False))
                    return cache[key]
                if self.counter-start>=budget: raise StopIteration('COUNTED_PHYSICAL_OPTIMIZER_BUDGET')
                cand=self.candidate(family,z,f'{stage}_{family}_{self.counter:03d}',stage.upper())
                row=self.eval(b,cand,stage)
                if row is None: raise BranchStarted()
                cache[key]=row
            return cache[key]
        def objective(z): return evaluate(z)['J_F_N_s']/self.base['J_F_N_s']
        def constraints(z): return np.concatenate([(1-np.asarray(v)).ravel() for v in evaluate(z)['constraints']['components'].values()])
        try:
            fit=minimize(objective,z0,method='COBYLA',bounds=[(-1,1)]*18,constraints={'type':'ineq','fun':constraints},options={'maxiter':budget,'rhobeg':.15 if stage=='quality' else .25,'tol':.015,'catol':0.0})
            base.append('OPTIMIZER_STATUS.jsonl',dict(family=family,stage=stage,success=bool(fit.success),message=str(fit.message),nfev=int(fit.nfev),x=fit.x,physical_new=self.counter-start))
        except BranchStarted: return
        except StopIteration as error:
            base.append('OPTIMIZER_STATUS.jsonl',dict(family=family,stage=stage,status=str(error),physical_new=self.counter-start))

    def decision_boundary(self,b):
        phase=b['task_state'].phase.value
        if self.child is None and not self.fork_done and phase=='OUTBOUND':
            self.fork_done=True
            if MODE.startswith('development'):
                if self.development(b): return self.control(b)
            else:
                selection=json.loads((S/'FROZEN_SELECTION.json').read_text())
                best=selection['best']['candidate'];secondary=selection['secondary']['candidate']
                rows=[self.candidate('B0',np.zeros(18),'B0_match','VALIDATION'),
                      {**best,'id':'frozen_best','stage':'VALIDATION'}]
                if MODE=='repeat':
                    rows=[self.candidate('B0',np.zeros(18),'B0_match','REPEAT'),
                          {**best,'id':'best_repeat_1','stage':'REPEAT'}, {**best,'id':'best_repeat_2','stage':'REPEAT'}]
                elif secondary['free_parameters']!=best['free_parameters']:
                    rows.append({**secondary,'id':'frozen_secondary','stage':'VALIDATION'})
                for cand in rows:
                    self.cache={}
                    if self.eval(b,cand,'repeat' if MODE=='repeat' else 'validation') is None: return self.control(b)
                if MODE=='repeat':
                    gate=base.mh.complete_gate('repeat_best_repeat_1','repeat_best_repeat_2');base.put('BEST_REPEAT_GATE.json',gate);assert gate['status']=='PASS'
                    gate=base.mh.complete_gate('repeat_best_repeat_1',selection['best']['id']);base.put('BEST_SELECTION_REPRODUCTION_GATE.json',gate);assert gate['status']=='PASS'
        self.control(b)

def main():
    lock=(S/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    condition=dict(name=MODE,seed=P.get('development_seed',P['seed']),prefix={}) if MODE.startswith('development') or MODE=='repeat' else next(c for c in P['validation_conditions'] if c['name']==MODE)
    ident=MODE+'_parent';dispatch(ident,kind='LEGAL_COMPLETE_PARENT',condition=condition)
    random.seed(condition['seed']);np.random.seed(condition['seed']);interface=OvernightInterface(condition)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ABSOLUTE_PHYSICS_STOP')))
    signal.alarm(max(1,int(P['physics_hard_stop_unix']-time.time())))
    base.put('STATE.json',dict(phase=MODE,owned_workers=[os.getpid()],next_action='serial counted physical attempts'))
    try:
        metric=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
        if interface.child is not None: os._exit(0)
        base.mh.event('END',ident,returncode=0,joined=True,task_valid=metric['task_valid']);assert metric['task_valid']
        base.sd.metric(ident)
        other=MODE+'_B0_original' if MODE.startswith('development') else MODE+'_B0_match'
        gate=base.mh.complete_gate(ident,other);base.put(MODE+'_PARENT_GATE.json',gate);assert gate['status']=='PASS'
        base.put(MODE+'_DONE.json',dict(unix=time.time(),status='COMPLETE',all_children_joined=True))
    except BaseException as error:
        actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind']
        base.put('reports/'+actual+'_ERROR.json',dict(unix=time.time(),error=str(error),traceback=traceback.format_exc()))
        if interface.child is not None: os._exit(1)
        if not any(r['event']=='END' and r['id']==ident for r in base.mh.records()): base.mh.event('END',ident,returncode=1,joined=True,error=str(error))
        base.put('PHYSICS_STOP.json',dict(unix=time.time(),reason=str(error),traceback=traceback.format_exc())); raise
    finally:
        if interface.child is None:
            signal.alarm(0)
            active=getattr(interface,'active_owned_child_pid',None)
            base.put('WORKER_EXIT_'+MODE+'.json',dict(unix=time.time(),pid=os.getpid(),owned_children_joined=active is None,active_child=active))

if __name__=='__main__': main()
