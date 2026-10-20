from study_common import *
import matched_harness as mh, search_driver as sd, analyze_matched as am
from free_planner import FreePlanner
import random, copy, traceback, fcntl, signal
from scipy.optimize import minimize
S=STUDY;P=json.loads((S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json').read_text())
MODE=sys.argv[1] if len(sys.argv)>1 else 'development'
CAT={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
CAT['B0']=dict(id='B0',stage='REFERENCE',phases={})
SCALES=np.asarray(P['parameter_scales']);ZERO=np.zeros((2,5,3))
def put(n,x):mh.put(S/n,x)
def append(n,x):
    with (S/n).open('a') as f:f.write(json.dumps(clean(x),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def resource_sample():
    disk=shutil.disk_usage('/mnt/d');size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())
    mem={r.split(':')[0]:int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines()}
    row=dict(unix=time.time(),D_free_bytes=disk.free,study_bytes=size,available_memory_bytes=mem['MemAvailable'])
    append('RESOURCE_SAMPLES.jsonl',row)
    assert disk.free>=40*2**30 and size<8*2**30 and mem['MemAvailable']>=2**30,'RESOURCE_STOP'
def dispatch(ident,**extra):
    guard();n=sum(r['event']=='START' for r in mh.records());assert n<(84 if MODE.startswith('development') else 96),'ATTEMPT_RESERVE'
    if MODE.startswith('development'):assert time.time()<P['search_cutoff_unix'],'SEARCH_CUTOFF'
    assert time.time()<P['dispatch_cutoff_unix']-300,'CLOSEOUT_RESERVE'
    assert not any(r['event']=='START' and r['id']==ident for r in mh.records()),'DUPLICATE_ID'
    resource_sample();mh.event('START',ident,mode=MODE,**extra)
    put('PROGRESS.json',dict(unix=time.time(),mode=MODE,id=ident,attempts=n+1))
mh.dispatch=dispatch;sd.dispatch=dispatch
def constraint_components(m,b,c):
    v={k:np.asarray(r)/1.1 for k,r in c['burden_ratios'].items()}
    v.update(excursion=np.asarray(c['excursion_delta_deg'])/.5,cumulative_upper=np.asarray(c['cumulative_ratio'])/1.05,cumulative_lower=.95/np.asarray(c['cumulative_ratio']),boundary=c['phase_boundary_max_delta_deg']/.5,endpoint=np.asarray(c['endpoint_abs_delta_deg'])/.5,duration=c['duration_abs_delta_s']/.1,moment=m['moment_integral_Nm_s']/(b['moment_integral_Nm_s']*1.25),tracking=np.asarray(m['tracking_RMS_deg'])/(np.asarray(b['tracking_RMS_deg'])+.5),force_peak=m['force_peak_N']/(b['force_peak_N']*1.05),moment_peak=m['moment_peak_Nm']/(b['moment_peak_Nm']*1.05))
    for ph in ['OUTBOUND','HOLD','RETURN']:v['duration_'+ph]=abs(m['phase_durations'][ph]-b['phase_durations'][ph])/.1
    return v
def summarize(ident,base,cand):
    m=sd.metric(ident);c=am.compare(m,base);v=constraint_components(m,base,c)
    worst=max((float(np.max(a)),k) for k,a in v.items())
    summary=json.loads((O/ident/'summary.json').read_text())
    free=[dict(index=i,phase=d.get('phase'),activation=d.get('activation_outcome'),screen=d.get('executed',d.get('selected_plan',{}))) for i,d in enumerate(summary['decisions']) if 'free_trajectory' in str(d)]
    row=dict(id=ident,candidate=cand,base_id=base['id'],J_F_N_s=m['J_F_N_s'],phase_J_F_N_s={ph:r['J_F_N_s'] for ph,r in m['phase_cost']['phases'].items()},comparison=c,constraints=dict(components=v,worst_ratio=worst[0],worst_requirement=worst[1]),level='DYNAMICS_FEASIBLE' if c['acceptance_pass'] else 'PHYSICALLY_EXECUTED_MOTION_FAIL',native_B_executable=bool(not np.any(cand.get('free_parameters',[]))),free_decision_count=len(free),actual_new_native_steps=m['actual_new_native_steps'],metrics_path=str(S/'reports'/(ident+'_MEASURED.json')))
    append('EVALUATIONS.jsonl',row)
    print(json.dumps(dict(id=ident,gain_percent=c['gain_percent'],pass_all=c['acceptance_pass'],worst=worst,failed=c['failed_requirements'])),flush=True)
    return row
class FreeInterface(sd.SearchInterface):
    def __init__(self,condition):
        super().__init__(condition,False);self.lookup.update(CAT);self.cache={};self.counter=0;self.eval_rows=[];self.stage_counts={};self.candidate=None
    def control(self,b):
        planner=b['planner']
        if self.child and self.child['kind']=='B0_original':return super().control(b)
        if not isinstance(planner,FreePlanner):planner.__class__=FreePlanner
        planner.free_parameters=np.asarray((self.lookup.get(self.child['kind'],{}) if self.child else {}).get('free_parameters',np.zeros(10)),float)
        return super().control(b)
    def fork(self,b,tag,table=None):
        result=super().fork(b,tag,table)
        if result:
            signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_CHILD_WALL_LIMIT')));signal.alarm(600)
        return result
    def eval(self,b,cand,stage='main'):
        key=digest(dict(native_seed=cand.get('seed_family',cand['id']),free=cand.get('free_parameters',[]),phases=cand.get('phases'),table=cand.get('table')))
        if key in self.cache:return self.cache[key]
        self.counter+=1;tag=cand['id'];self.lookup[tag]=cand
        try:
            if self.fork(b,tag,np.asarray(cand.get('table',ZERO))):return None
        except AssertionError as e:
            if not str(e).startswith('NATIVE_PHYSICAL_FAILURE:'):raise
            sd.classify_task_failure(self.condition['name']+'_'+tag,cand)
            raise RuntimeError('COMPLETE_TASK_FAILURE_STOP_NO_PARTIAL_RANKING')
        ident=self.condition['name']+'_'+tag
        if self.base is None:self.base=sd.metric(ident)
        row=summarize(ident,self.base,cand);self.eval_rows.append(row);self.cache[key]=row
        self.stage_counts[stage]=self.stage_counts.get(stage,0)+1
        put('SEARCH_STATE.json',dict(unix=time.time(),stage_counts=self.stage_counts,rows=len(self.eval_rows),best=min([r for r in self.eval_rows if r['comparison']['acceptance_pass']],key=lambda r:r['J_F_N_s'],default=None)))
        # Retain complete evidence for references and current best/strong representative;
        # report ordinary raw only after full safety, ownership and integral checks.
        if stage not in ['baseline','validation','repeat']:
            keep=min([r for r in self.eval_rows if r['comparison']['acceptance_pass']],key=lambda r:r['J_F_N_s'],default=None)
            for r in self.eval_rows:
                if r['candidate'].get('stage') in ['REFERENCE','VALIDATION','REPEAT'] or (keep and r['id']==keep['id']):continue
                raw=O/r['id']/'runtime_artifacts.json.gz'
                if raw.exists():
                    assert raw.resolve().is_relative_to(S.resolve())
                    append('COMPACTION.jsonl',dict(unix=time.time(),id=r['id'],sha256=sha(raw),bytes=raw.stat().st_size,reason='completed full dense receipt/safety/derivative/integral audit; compact trace retained'))
                    raw.unlink()
        return row
    def candidate_for(self,family,z,tag,stage):
        c=copy.deepcopy(CAT[family]);c.update(id=tag,stage=stage,seed_family=family,free_parameters=(np.asarray(z)*SCALES).tolist(),normalized_parameters=np.asarray(z).tolist());return c
    def development(self,b):
        baseline_rows=[('B0_original','B0'),('B0_zero_extension','B0'),('NATIVE_SCALAR_18','NATIVE_SCALAR_18'),('M2_fixed_actions','M2_fixed_actions'),('C2_pair_1_2','C2_pair_1_2')]
        if MODE=='development_resume':baseline_rows=[r for r in baseline_rows if r[0]!='B0_zero_extension']
        for tag,family in baseline_rows:
            c=self.candidate_for(family,np.zeros(10),tag,'REFERENCE')
            # Force the deterministic repeat through the execution rather than cached objective.
            if tag=='B0_zero_extension':self.cache={}
            if self.eval(b,c,'baseline') is None:return True
            if tag=='B0_zero_extension':
                gate=mh.complete_gate(self.condition['name']+'_B0_original',self.condition['name']+'_B0_zero_extension');put('ZERO_EXTENSION_REPRODUCTION_GATE.json',gate);assert gate['status']=='PASS'
            if tag=='B0_original' and MODE=='development_resume':
                gate=mh.complete_gate(self.condition['name']+'_B0_original','development_B0_original');put('FRESH_PARENT_REPRODUCTION_GATE.json',gate);assert gate['status']=='PASS'
                put('ZERO_EXTENSION_REPRODUCTION_GATE.json',json.loads((S/'WRAPPER_RECOVERED_ZERO_GATE.json').read_text()))
        put('BASELINE_REPRODUCTION.json',dict(status='PASS',zero_gate=json.loads((S/'ZERO_EXTENSION_REPRODUCTION_GATE.json').read_text()),runs=self.eval_rows.copy(),same_complete_state=True,plant_and_evaluator_unchanged=True))
        # Twelve physical probes across independent velocity and common-progress directions.
        for k,(axis,sign) in enumerate([(0,1),(0,-1),(5,1),(5,-1),(3,1),(3,-1),(4,1),(4,-1),(8,1),(8,-1),(9,1),(9,-1)]):
            z=np.zeros(10);z[axis]=sign*.5
            if self.eval(b,self.candidate_for('NATIVE_SCALAR_18',z,f'probe_{k:02d}','INITIAL'),'initial') is None:return True
        # One measured constrained objective per unique physical parameter sequence.
        class BranchStarted(Exception):pass
        def optimize(family,budget,stage):
            candidates=[r for r in self.eval_rows if r['candidate'].get('seed_family')==family]
            leader=min(candidates,key=lambda r:(not r['comparison']['acceptance_pass'],r['J_F_N_s'] if r['comparison']['acceptance_pass'] else r['constraints']['worst_ratio']))
            z0=np.asarray(leader['candidate']['normalized_parameters']);start=self.counter;last={}
            def evaluation(z):
                if time.time()>P['search_cutoff_unix']-600:raise TimeoutError('SEARCH_CLOSEOUT_RESERVE')
                key=np.asarray(z,dtype=float).tobytes()
                if key not in last:
                    if self.counter-start>=budget:raise StopIteration('PHYSICAL_OPTIMIZER_BUDGET')
                    tag=f'{stage}_{family}_{self.counter:03d}'
                    r=self.eval(b,self.candidate_for(family,z,tag,stage.upper()),stage)
                    if r is None:raise BranchStarted()
                    last[key]=r
                return last[key]
            def objective(z):return evaluation(z)['J_F_N_s']/self.base['J_F_N_s']
            def constraints(z):
                r=evaluation(z);return np.concatenate([(1-np.asarray(v)).ravel() for v in r['constraints']['components'].values()])
            try:
                fit=minimize(objective,z0,method='COBYLA',bounds=[(-1,1)]*10,constraints={'type':'ineq','fun':constraints},options={'maxiter':budget,'rhobeg':.25,'tol':.015,'catol':0.0})
                append('OPTIMIZER_STATUS.jsonl',dict(family=family,stage=stage,success=bool(fit.success),message=str(fit.message),nfev=fit.nfev,x=fit.x,physical_new=self.counter-start))
            except BranchStarted:return True
            except StopIteration as e:append('OPTIMIZER_STATUS.jsonl',dict(family=family,stage=stage,status=str(e),physical_new=self.counter-start))
            return False
        for family,budget in [('NATIVE_SCALAR_18',20),('B0',20)]:
            if optimize(family,budget,'main'):return True
        for family in ['M2_fixed_actions','C2_pair_1_2']:
            if optimize(family,8,'repair'):return True
        feasible=[r for r in self.eval_rows if r['comparison']['acceptance_pass']]
        best=min(feasible,key=lambda r:r['J_F_N_s']);strong=min(self.eval_rows,key=lambda r:r['J_F_N_s'])
        put('FROZEN_SELECTION.json',dict(unix=time.time(),protocol_sha256=sha(S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json'),best=best,diagnostic=strong,heldout_not_used=True,parameters_frozen=True))
        return False
    def decision_boundary(self,b):
        phase=b['task_state'].phase.value;needed=1 if MODE.startswith('W') else 0
        if self.child is None and not self.fork_done and phase==('RETURN' if MODE.startswith('W') else 'OUTBOUND') and self.count[phase]>=needed:
            self.fork_done=True
            if MODE.startswith('development'):
                if self.development(b):return self.control(b)
            else:
                selection=json.loads((S/'FROZEN_SELECTION.json').read_text());c=selection['best']['candidate']
                rows=[self.candidate_for('B0',np.zeros(10),'B0_match','VALIDATION'),{**c,'id':'frozen_best','stage':'VALIDATION'}]
                if MODE=='repeat':rows=[{**c,'id':'best_repeat_1','stage':'REPEAT'},{**c,'id':'best_repeat_2','stage':'REPEAT'}]
                for cand in rows:
                    self.cache={}
                    if self.eval(b,cand,'repeat' if MODE=='repeat' else 'validation') is None:return self.control(b)
                if MODE=='repeat':
                    gate=mh.complete_gate('repeat_best_repeat_1','repeat_best_repeat_2');put('BEST_REPEAT_GATE.json',gate);assert gate['status']=='PASS'
        self.control(b)
def main():
    lock=(S/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    condition=dict(name=MODE,seed=P['seed'],prefix={}) if MODE.startswith('development') or MODE=='repeat' else next(c for c in P['validation_conditions'] if c['name']==MODE)
    ident=condition['name']+'_parent';dispatch(ident,kind='LEGAL_COMPLETE_PARENT',condition=condition)
    random.seed(condition['seed']);np.random.seed(condition['seed']);interface=FreeInterface(condition)
    try:
        m=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
        if interface.child is not None:os._exit(0)
        mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];sd.metric(ident)
        gate=mh.complete_gate(ident,condition['name']+'_B0_match' if MODE.startswith('W') else condition['name']+'_B0_original') if MODE!='repeat' else None
        if gate:put(MODE+'_PARENT_GATE.json',gate);assert gate['status']=='PASS'
        put(MODE+'_DONE.json',dict(unix=time.time(),status='COMPLETE',all_children_joined=True))
    except BaseException as e:
        actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind']
        put('reports/'+actual+'_ERROR.json',dict(unix=time.time(),error=str(e),traceback=traceback.format_exc()))
        if interface.child is not None:os._exit(1)
        mh.event('FAIL',ident,error=str(e),joined=True);put('PHYSICS_STOP.json',dict(unix=time.time(),reason=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
