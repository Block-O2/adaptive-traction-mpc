"""Conditional, preregistered single traditional refinement; no retuning."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,traceback,ast,itertools
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'source'),str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
from v6_data import group as collect
from v6_summarize import blend,evaluations
def read(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):
    q=P/n;q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def decision(kind,**extra):
    with (P/'RESEARCH_DECISIONS.jsonl').open('a') as s:
        s.write(json.dumps(dict(unix=time.time(),kind=kind,**extra),ensure_ascii=False)+'\n')
def run(g):
    with (P/'logs'/f'{g}_adaptive_supervisor.log').open('w') as out:
        rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),f'experiments/{g}.json'],
                          env=dict(os.environ,ACL2_PACKAGE=str(P)),stdout=out,stderr=subprocess.STDOUT,
                          timeout=max(1,deadline-time.time()-2400)).returncode
    assert rc==0,'ADAPTIVE_RULE_JOB_FAILED:'+g
    return {r['tag']:r for r in collect(g,wrench=True) if r['horizon_s']==.5}
def compare(g,rows,reference_group=None):
    ref=rows if reference_group is None else {r['tag']:r for r in read('data/'+reference_group+'.json') if r['horizon_s']==.5}
    b,c,x=(ref['BEST'],ref['COMPOSE'],rows['RULE'])
    def vector(r):return np.r_[r['metrics']['full_jerk_RMS_deg_s3'],r['metrics']['wrench']['force_norm_rate_RMS_N_s']]
    bv,cv,xv=map(vector,[b,c,x]);ret=(bv-xv)/(bv-cv)
    return dict(group=g,comparison_reference=reference_group or g,
        all_original_qualified=all(r['qualified'] for r in [b,c,x]),
        retention_hip_knee_force_rate=ret.tolist(),retention_90pct_pass=bool(np.all(ret>=.9)),
        RULE_JF_reduction_vs_COMPOSE=c['metrics']['full_JF']-x['metrics']['full_JF'],
        RULE_JM_increase_vs_COMPOSE=x['metrics']['full_JM']-c['metrics']['full_JM'],
        RULE_JF_reduction_vs_BLEND=ref['BLEND']['metrics']['full_JF']-x['metrics']['full_JF'],
        RULE_JM_increase_vs_BLEND=x['metrics']['full_JM']-ref['BLEND']['metrics']['full_JM'],
        RULE_vs_BEST_percent=((xv/bv-1)*100).tolist(),
        full_costs={tag:dict(JF=r['metrics']['full_JF'],JM=r['metrics']['full_JM'],qualified=r['qualified'])
                    for tag,r in dict(ref,**rows).items()})
started=time.time();deadline=read('ACTIVATION.json')['hard_stop_unix'];status='WAITING';results=[];reason=None
put('owned/ADAPTIVE_RULE_DRIVER_START.json',dict(pid=os.getpid(),started_unix=started,
    source_sha256=sha(Path(__file__)),deadline_unix=deadline))
try:
    while not (P/'jobs/CAMPAIGN_DONE.json').exists():
        if (P/'jobs/CAMPAIGN_ERROR.json').exists():raise RuntimeError('MAIN_CAMPAIGN_REQUIRES_REVIEW')
        if time.time()>deadline-2400:raise RuntimeError('NO_NEW_PHYSICS_WITH_CLOSURE_RESERVE')
        time.sleep(5)
    core=[r for r in blend() if r['role'].startswith('independent')];ev=evaluations()
    if ev['meaningful_independent_increment_states']:
        status='REVIEW_REQUIRED';reason='Prioritize independent Critic benefit reproduction before optional rule.'
    elif len(core)!=2 or not all(r['all_three_original_qualified'] and r['retention_90pct_pass'] for r in core):
        status='NOT_RUN';reason='Prerequisite: both frozen BLEND confirmations must pass original gate and90% retention.'
    else:
        # Actual observed attempt duration, plus all 15 attempts, 40min closeout and5min margin.
        evs=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()]
        begin={r['id']:r['unix'] for r in evs if r['event']=='START'}
        spans=[r['unix']-begin[r['id']] for r in evs if r['event']=='END' and r['id'] in begin and not r['id'].endswith('_parent')]
        allowance=max(120.,float(np.quantile(spans,.9)))
        required=15*allowance+2400+300
        if deadline-time.time()<required:
            status='NOT_RUN';reason=f'Actual timing reserve: need{required:.0f}s, have{deadline-time.time():.0f}s.'
        else:
            contract=read('freeze/ADAPTIVE_FIXED_RULE_PROTOCOL.json')
            assert sha(P/'source/v6_fixed_rule_worker.py')==contract['worker_sha256'],'REGISTERED_RULE_SOURCE_CHANGED'
            put('freeze/ADAPTIVE_RULE_ACTIVATED.json',dict(activated_unix=time.time(),
                remaining_wall_s=deadline-time.time(),measured_p90_candidate_wall_s=allowance,
                total_required_wall_s=required,contract_sha256=sha(P/'freeze/ADAPTIVE_FIXED_RULE_PROTOCOL.json'),
                configurations_sha256={g:sha(P/'experiments'/f'{g}.json') for g in ['RULE_DEV','RULE_T1','RULE_T2']},
                baseline_results=core,main_independent_critic_increment_states=ev['meaningful_independent_increment_states']))
            decision('ADAPTIVE_SINGLE_RULE_ACTIVATED',hypothesis=contract['hypothesis'],maximum_START=15,
                     scope='traditional no-retune refinement after completed A-D; independent main results immutable')
            dev=run('RULE_DEV')
            src=P/'runtime/control/base_campaign.py';tree=ast.parse(src.read_text())
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw')
            scope=dict(np=np,itertools=itertools,array_items=array_items)
            exec(compile(ast.Module(body=[fn],type_ignores=[]),str(src),'exec'),scope)
            identity=scope['compare_raw'](P/'runtime/source/results/RULE_DEV_B',P/'runtime/source/results/DEV_O1_B')
            put('audit/RULE_DEV_MATCHED_B_RAW_IDENTITY.json',identity)
            assert identity['status']=='PASS','RULE_DEVELOPMENT_REFERENCE_NOT_MATCHED'
            r=compare('RULE_DEV',dev,'DEV_O1');results.append(r)
            put('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json',dict(status='DEVELOPMENT_COMPLETE',rows=results))
            if not (r['all_original_qualified'] and r['retention_90pct_pass'] and r['RULE_JF_reduction_vs_COMPOSE']>0):
                status='STOPPED_AT_REGISTERED_DEVELOPMENT_GATE';reason='No retuning; preserve failed development result.'
            else:
                put('freeze/ADAPTIVE_RULE_CONFIRMATIONS_FROZEN.json',dict(frozen_unix=time.time(),
                    rule_sha256=sha(P/'freeze/ADAPTIVE_FIXED_RULE_PROTOCOL.json'),
                    worker_sha256=sha(P/'source/v6_fixed_rule_worker.py'),development_result=r,
                    test_groups=['RULE_T1','RULE_T2'],test_results_seen=False,retention_threshold=.9))
                for g in ['RULE_T1','RULE_T2']:results.append(compare(g,run(g)))
                status='COMPLETED_FROZEN_CONFIRMATIONS'
    put('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json',dict(status=status,reason=reason,rows=results,
        started_unix=started,ended_unix=time.time(),scope='one preregistered traditional rule; no model retuning or broad search'))
except BaseException as e:
    status='REVIEW_REQUIRED';reason=str(e)
    put('jobs/ADAPTIVE_RULE_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
    raise
finally:
    put('owned/ADAPTIVE_RULE_DRIVER_END.json',dict(pid=os.getpid(),ended_unix=time.time(),status=status,reason=reason))
    print('ADAPTIVE_RULE',status,reason,flush=True)
