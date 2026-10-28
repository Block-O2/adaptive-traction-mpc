"""Independent bounded package preparation; no historical writes or fitting."""
from pathlib import Path
import os, sys, json, time, datetime, shutil, subprocess, hashlib
sys.dont_write_bytecode = True
OLD = Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
S = OLD.parent / 'm2_comprehensive_coordination_search_v1'
ROOT = Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source')
W = Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
T0 = datetime.datetime.fromisoformat('2026-10-08T12:59:12+00:00').timestamp()
QHASH = '3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''): h.update(b)
    return h.hexdigest()
def save(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
def git_snapshot():
    def git(*args):
        return subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,check=True).stdout
    return dict(branch=git('branch','--show-current').decode(),HEAD=git('rev-parse','HEAD').decode(),status=git('status','--porcelain=v1').decode(),index_sha256=sha(ROOT/'.git/index'),staged_diff_sha256=hashlib.sha256(git('diff','--cached','--binary')).hexdigest())
def main():
    assert not S.exists(), 'Existing package must never be reset'
    assert sha(OLD/'weights/frozen_Q_v1/weights.npz') == QHASH
    S.mkdir()
    for d in ('reports','preservation','queue','logs','output','inputs','versions','checkpoints'): (S/d).mkdir()
    save(S/'preservation/GIT_BEFORE.json',git_snapshot())
    protected={str(p):sha(p) for p in OLD.rglob('*') if p.is_file()}
    save(S/'preservation/HISTORY_BEFORE.json',protected)
    prior=json.loads((OLD/'preservation/PROTECTED_BEFORE.json').read_text())
    save(S/'preservation/OTHER_HISTORY_BEFORE.json',{p:sha(p) for p in prior})
    reloc=[]
    for d in ('source','deps','code','native','build','weights'):
        shutil.copytree(OLD/d,S/d,ignore=shutil.ignore_patterns('results','__pycache__','.git','temp.*'))
        for p in (S/d).rglob('*'):
            if not p.is_file() or p.suffix not in ('.py','.json','.xml','.yaml','.yml','.toml','.sh'): continue
            text=p.read_text(); new=text.replace(str(OLD),str(S)).replace("'b_fast_jitter_m2_host_v1'","'m2_comprehensive_coordination_search_v1'").replace('"b_fast_jitter_m2_host_v1"','"m2_comprehensive_coordination_search_v1"')
            if text != new:
                before=sha(p);p.write_text(new);reloc.append(dict(path=str(p.relative_to(S)),before_sha256=before,after_sha256=sha(p),change='exact package-path relocation only'))
    (S/'source/results').mkdir(exist_ok=True)
    save(S/'preservation/SOURCE_RELOCATION.json',reloc)
    for p in (OLD/'versions').iterdir():
        if p.is_file(): shutil.copy2(p,S/'versions'/p.name)
    for rel in ('C13_LOCAL_EQUIVALENCE.json','C12_LOCAL_EQUIVALENCE.json','HISTORICAL_K3_DESIGN_REFERENCE.json','SHARED_COORDINATION_ACTION_CONTRACT.json'):
        shutil.copy2(OLD/'output'/rel,S/'output'/rel)
    shutil.copy2(OLD/'reports/OFFLINE_INTERFACE_GATE.json',S/'reports/OFFLINE_INTERFACE_GATE.json')
    shutil.copy2(OLD/'TIMING_BASELINE.json',S/'TIMING_BASELINE.json')
    plan=dict(t0_unix=T0,t0_basis='first observed UTC clock at task entry',hard_stop_unix=T0+9000,dispatch_cutoff_unix=T0+7200,physics_budget=12,max_physics_budget=12,physical_dt_s=.00025,control_dt_s=.005,threads=1,bytes_target=4*2**30,single_physics_owner=True,no_auto_resume=True)
    save(S/'RUN_PLAN.json',plan)
    save(S/'TASK_LEDGER.json',{}); (S/'ATTEMPTS.jsonl').touch()
    (S/'PROGRESS.md').write_text('# Frozen M2 generalization and attribution v1\n')
    save(S/'STATE.json',dict(status='ACTIVE',phase='PREPARATION',active=[],physics_attempts=0,t0_unix=T0))
    protocol=OLD.parent/'b_native_q_realtime_integration_v1/versions/LEGAL_PREFIX_STABILITY_PROTOCOL.json'
    registered=json.loads(protocol.read_text())['rows']
    prefixes=[next(r['prefix'] for r in registered if r['pair']==j) for j in (1,2)]
    old_prefixes=[json.loads(p.read_text()).get('prefix',{}) for p in (OLD/'queue').glob('*.json')]
    assert all(p not in old_prefixes for p in prefixes), 'Must be independent of preceding host package'
    pairs=[];counter=1
    for j,prefix in enumerate(prefixes,1):
        for k,seed in enumerate((2026100801,2026100802),1):
            pair=f'deviation_P{j}_seed{k}'; order=['M0','M2'] if (j+k)%2==0 else ['M2','M0'];ids=[]
            for method in order:
                ident=f'{counter:03d}_{pair}_'+('B' if method=='M0' else 'M2'); counter+=1;ids.append(ident)
                cfg=json.loads((OLD/'queue/013_deviation_pair1_M2.json').read_text())
                cfg.update(id=ident,seed=seed,method=method,prefix=prefix,pair_id=pair,pair_condition='deviation',pair_replicate=k,weights=str(S/'weights/frozen_Q_v1'),qualification_group='PREREGISTERED_INDEPENDENT_PREFIX_HOST_RESEARCH')
                cfg.pop('durable_config_path',None)
                save(S/'queue'/(ident+'.json'),cfg)
            pairs.append(dict(pair_id=pair,ids=ids,seed=seed,prefix=prefix,prefix_registry_pair=j))
    reg=dict(status='PASS',registered_unix=time.time(),pairs=pairs,same_B_C13=True,matched_instrumentation=True,both_strict55_guard=False,physical_bridge_guard_ms=40,all_failures_retained=True)
    save(S/'reports/PAIR_REGISTRATION.json',reg)
    contract=json.loads((OLD/'EXPERIMENT_CONTRACT.json').read_text())
    contract.update(schema='FROZEN_M2_GENERALIZATION_ATTRIBUTION_v1',registered_unix=time.time(),budget=plan,hypotheses=['New registered legal prefixes may or may not reproduce lower J_F','Fixed-candidate masked Q differences may be state independent','RETURN benefits require force-duration and multiobjective decomposition'],pair_plan=pairs,setup='Two pre-existing registered prefixes new to preceding host package, two matched seeds; same single high-ROM nominal Human; not unseen-Human validation',exclusions='No outcome exclusion; pair valid only full physical/safety and causal PASS with complete exports, matched configurations, verified Q identity and nonzero M2 native execution',stop_policy='Stop all physical dispatch at safety, causal ownership, identity, export, unstable-resource, repeated-identical-failure or budget failure',phase_attribution='Left-endpoint TASK trace quadrature, exact transition partition, symmetric product decomposition; retain phase-clock durations and integrated durations',repair_policy='No B/Q redesign, no safety threshold changes; only package-path relocation',comparator='NOT_RUN if real-arithmetic fixed-ranking equivalence proven; preserve deployed float32 close-rank safeguards',prefix_source=dict(path=str(protocol),sha256=sha(protocol)),statistical_scope='Four descriptive matched pairs; no population-level inference')
    save(S/'EXPERIMENT_MANIFEST.json',contract)
    save(S/'EXPERIMENT_CONTRACT.json',contract);save(S/'QUALIFICATION_CONTRACT.json',contract)
    shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/c03c488d-1070-4c57-878d-c0a0cf193523/已粘贴的文本.txt',S/'USER_REQUEST.txt')
    ledger=json.loads((OLD/'TASK_LEDGER.json').read_text());axes=[json.loads(p.read_text()) for p in (OLD/'reports').glob('*_AXES.json')]
    m2=[r for r in axes if r.get('PHYSICAL_TASK_VALID')=='PASS' and r.get('HOST_EXECUTION_CAUSAL_VALID')=='PASS' and ledger[r['id']]['config'].get('method')=='M2']
    audit=dict(status='PASS',prior_attempts=len(ledger),prior_START_count=sum(json.loads(l)['event']=='START' for l in (OLD/'ATTEMPTS.jsonl').read_text().splitlines()),prior_END_count=sum(json.loads(l)['event']=='END' for l in (OLD/'ATTEMPTS.jsonl').read_text().splitlines()),valid_M2_runs=len(m2),nonzero_executed_plans=sum(r['nonzero_execution_count'] for r in m2),associated_native_steps=sum(r['nonzero_native_steps'] for r in m2),valid_M2_ids=[r['id'] for r in m2],source_paths=[str(OLD/'TASK_LEDGER.json'),str(OLD/'ATTEMPTS.jsonl')],full_export_denominator_only=True)
    assert (audit['valid_M2_runs'],audit['nonzero_executed_plans'],audit['associated_native_steps'])==(6,25,143645)
    save(S/'reports/PREVIOUS_DENOMINATOR_AUDIT.json',audit)
    for p in W.glob('*.py'): shutil.copy2(p,S/'code'/p.name)
    save(S/'reports/PREFLIGHT.json',dict(status='PASS',Q_sha256=sha(S/'weights/frozen_Q_v1/weights.npz'),previous_denominator=audit,registered_pairs=4,registered_runs=8,path_only_relocations=len(reloc),hard_stop_unix=T0+9000,dispatch_cutoff_unix=T0+7200))
    print(json.dumps(dict(status='PASS',path=str(S),previous_denominator=audit,registered_pairs=pairs),ensure_ascii=False))
if __name__=='__main__': main()
