"""Resumable offline CEM teacher generation through frozen scientific runtime."""
from __future__ import annotations
import csv,gzip,hashlib,json,os,platform,subprocess,sys,time,traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from coordination_space import DIMENSIONS,NAMES,LOW,HIGH,neutral,known_good,test_space

R=Path(__file__).resolve().parents[4]; S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/best_known_coordination_search_v2'; RAW=S/'results/best_known_coordination_search_v2'
RUNS=RAW/'runs'; PROPOSALS=RAW/'proposals'; RUNNER=Path(__file__).with_name('rollout_v2.py')
C=json.loads((D/'SEARCH_CONTRACT.json').read_text()); F=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text())
CONDITIONS=C['conditions']; ARMS=('MATCHED','NATIVE')
ENV={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
for p in (RUNS,PROPOSALS):p.mkdir(parents=True,exist_ok=True)
START_FILE=RAW/'start.json'
def save(path,x):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n');temp.replace(path)
def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def check_frozen():
    bad=[name for name,h in {**F['protected_files'],**F['evidence_files']}.items() if sha(R/name)!=h]
    if bad:raise RuntimeError('PROTECTED_FINGERPRINT_CHANGED:'+str(bad))
    return len(F['protected_files'])
def baseline(cond,arm):return read(RUNS/f'A_{cond}_{arm}_baseline_0/rollout_result.json')
def eligible(record,base,arm):
    if record.get('status')!='VALID':return False,False,None
    residual={p:record[p.lower()+'_duration_s']-base[p.lower()+'_duration_s'] for p in ('OUTBOUND','RETURN')}
    same=all(len(record.get('planned_segments',{}).get(p,[]))==len(base.get('planned_segments',{}).get(p,[])) for p in residual)
    isolated=same and max(abs(x) for x in residual.values())<=C['matched_tolerance_s']+1e-9
    return arm=='NATIVE' or isolated,isolated,residual
def compress_raw(out,record):
    storage=record.get('raw_storage',{})
    for name,h in record.get('raw_files_sha256',{}).items():
        path=out/name
        if name in storage:
            if sha(out/storage[name]['stored_path'])!=storage[name]['stored_sha256']:raise RuntimeError('stored raw corruption')
            continue
        if path.suffix=='.json' and path.exists():
            dest=path.with_suffix(path.suffix+'.gz'); temp=dest.with_suffix(dest.suffix+'.tmp')
            original_bytes=path.stat().st_size
            with path.open('rb') as inp, temp.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=1,mtime=0) as z:
                for chunk in iter(lambda:inp.read(1024*1024),b''):z.write(chunk)
            checked=hashlib.sha256()
            with gzip.open(temp,'rb') as z:
                for chunk in iter(lambda:z.read(1024*1024),b''):checked.update(chunk)
            if checked.hexdigest()!=h:raise RuntimeError('lossless archive verification failed:'+name)
            temp.replace(dest)
            storage[name]={'stored_path':str(dest.relative_to(out)),'stored_sha256':sha(dest),'original_sha256':h,
                           'original_bytes':original_bytes,'stored_bytes':dest.stat().st_size,'codec':'gzip','decompression_verified':True}
            record['raw_storage']=storage;save(out/'rollout_result.json',record)
            path.unlink() # Only exact newly-generated file after verified local lossless copy.
        elif path.exists():
            if sha(path)!=h:raise RuntimeError('raw hash mismatch:'+name)
            storage[name]={'stored_path':name,'stored_sha256':h,'original_sha256':h,'codec':'none','stored_bytes':path.stat().st_size}
    record['raw_storage']=storage;save(out/'rollout_result.json',record)
def execute(entry):
    ident=entry['run_id'];spec=entry['spec'];out=RUNS/ident;path=out/'rollout_result.json'
    proposal=PROPOSALS/(ident+'.json')
    if proposal.exists():
        if read(proposal)!=entry:raise RuntimeError('immutable proposal conflict:'+ident)
    else:save(proposal,entry)
    if path.exists():
        r=read(path)
        if r['status']=='RUNNING':
            r.update(status='INTERRUPTED',failure_reason='prior process stopped before final record; preserve incomplete attempt')
            save(path,r)
        compress_raw(out,r);return r
    if time.time()-read(START_FILE)['epoch']>C['maximum_wall_hours']*3600:raise RuntimeError('WALL_CAP')
    command=[sys.executable,str(RUNNER),'--condition',entry['condition'],'--arm',entry['arm'],'--run-id',ident]
    if spec is not None:
        sp=RAW/(ident+'_spec.json');save(sp,spec);command+=['--pattern-file',str(sp)]
    began=time.monotonic()
    try:
        p=subprocess.run(command,env=ENV,capture_output=True,text=True,timeout=C['timeout_per_candidate_s'])
        log={'command':command,'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-4000:]}
    except subprocess.TimeoutExpired as ex:
        log={'command':command,'timeout_s':C['timeout_per_candidate_s'],'error':str(ex)}
    out.mkdir(parents=True,exist_ok=True);save(out/'process_log.json',log)
    r=read(path) if path.exists() else {'run_id':ident,'status':'EXCEPTION','failure_reason':'missing simulation result','condition_id':entry['condition'],'arm':entry['arm'],'pattern':spec}
    if r.get('status')=='RUNNING':r.update(status='TIMEOUT',failure_reason='subprocess timeout; no scientific result promoted')
    r.update(wrapper_elapsed_s=time.monotonic()-began,proposal_sha256=sha(proposal))
    save(path,r);compress_raw(out,r)
    print(json.dumps({'phase':entry['phase'],'run':ident,'status':r['status'],'J_F':r.get('J_F_task_n_s'),'rollout_s':r.get('elapsed_host_s')}),flush=True)
    return r
def entry(cond,arm,ident,spec,phase,**extra):return {'condition':cond,'arm':arm,'run_id':ident,'spec':spec,'phase':phase,**extra}
def spec(level,p):return {'level':level,'parameters':list(map(float,p)),'matched_duration_factor':1.3}

def phase_a_pair(pair):
    ci,ai=pair;c=CONDITIONS[ci]['id'];arm=ARMS[ai]
    rng=np.random.default_rng(20261001+ci*100+ai)
    zero=None if arm=='NATIVE' else spec(1,neutral(1))
    fixed=spec(1,known_good(1)); small=neutral(1);small[:2]=rng.uniform(-.01,.01,2)
    diverse=rng.uniform(LOW[:6],HIGH[:6]);diverse[4:6]=0
    for tag,p in [('baseline_0',zero),('baseline_1',zero),('fixed_0',fixed),('fixed_1',fixed),('small',spec(1,small)),('diverse',spec(1,diverse))]:
        execute(entry(c,arm,f'A_{c}_{arm}_{tag}',p,'A',level=1,initialization=tag))
def gate_a():
    rows=[];old=S/'docs/coordination_pacing_exploration_v1'
    hist=read(old/'BASELINE_MATRIX_VALIDATION_V2.json')
    for c in CONDITIONS:
        for arm in ARMS:
            a=baseline(c['id'],arm);b=read(RUNS/f'A_{c["id"]}_{arm}_baseline_1/rollout_result.json')
            h=next(x for x in hist['rows'] if x['condition_id']==c['id'])
            expected=h['matched_baseline_J_F_task_n_s' if arm=='MATCHED' else 'native_baseline_J_F_task_n_s']
            fixed=read(RUNS/f'A_{c["id"]}_{arm}_fixed_0/rollout_result.json');replay=read(RUNS/f'A_{c["id"]}_{arm}_fixed_1/rollout_result.json')
            error=abs(a.get('J_F_task_n_s',-1)-b.get('J_F_task_n_s',-2))
            historical=abs(a.get('J_F_task_n_s',-1)-expected)
            good,iso,residual=eligible(fixed,a,arm)
            fixed_repeat=(fixed['status']==replay['status'] and (fixed['status']!='VALID' or abs(fixed['J_F_task_n_s']-replay['J_F_task_n_s'])<=1e-6))
            passed=a['status']==b['status']=='VALID' and error<=1e-6 and historical<=1e-6 and fixed_repeat
            if c['id'] in ('sync_120','variable_start_120') and arm=='MATCHED':passed=passed and good and fixed['J_F_task_n_s']<a['J_F_task_n_s']
            rows.append({'condition':c['id'],'arm':arm,'pass':bool(passed),'replay_error_n_s':error,'historical_error_n_s':historical,
                         'fixed_valid':good,'fixed_repeat':fixed_repeat,'fixed_J_F':fixed.get('J_F_task_n_s'),'fixed_isolated':iso,'fixed_residual_s':residual})
    result={'status':'PASS' if all(r['pass'] for r in rows) else 'FAIL','rows':rows,'fingerprints_checked':check_frozen()}
    save(D/'PHASE_A_GATE.json',result)
    return result

def draw(rng,mean,std):
    for _ in range(2000):
        p=rng.normal(mean,std)
        if np.all(p>=LOW[:len(p)]) and np.all(p<=HIGH[:len(p)]):return p
    # Domain-only failure has no scientific rollout. Uniform valid-domain fallback is explicit.
    return rng.uniform(LOW[:len(p)],HIGH[:len(p)])
def pair_entries(cond,arm):return [read(p) for p in sorted(PROPOSALS.glob('*.json')) if (x:=read(p))['condition']==cond and x['arm']==arm]
def rankable_entries(cond,arm):
    base=baseline(cond,arm);good=[]
    for e in pair_entries(cond,arm):
        path=RUNS/e['run_id']/'rollout_result.json'
        if path.exists():
            r=read(path)
            if eligible(r,base,arm)[0]:good.append((r['J_F_task_n_s'],e,r))
    return sorted(good,key=lambda x:x[0])
def search_pair(pair):
    ci,ai=pair;cond=CONDITIONS[ci]['id'];arm=ARMS[ai];base=baseline(cond,arm)
    for level in (1,2,3):
        dim=DIMENSIONS[level];span=HIGH[:dim]-LOW[:dim]
        for restart in range(3):
            rng=np.random.default_rng(20261001+1000*ci+100*ai+10*level+restart)
            mean=neutral(level) if restart==0 else known_good(level) if restart==1 else neutral(level)
            if restart==2:
                randoms=[v for v in rankable_entries(cond,arm) if v[1].get('initialization') in ('small','diverse')]
                if randoms:mean[:6]=randoms[0][1]['spec']['parameters']
                else:mean[:2]=rng.uniform(-.01,.01,2)
            std=span*.15;memory=[]
            for generation in range(2):
                points=[mean.copy()]
                if memory:points.append(memory[0][1].copy())
                elif level>1:
                    prior=[x for x in rankable_entries(cond,arm) if x[1]['spec'] is not None]
                    if prior:
                        candidate=neutral(level);prev=prior[0][1]['spec']['parameters'];candidate[:min(dim,len(prev))]=prev[:dim]
                        points.append(candidate)
                while len(points)<3:points.append(draw(rng,mean,std))
                scored=[]
                for j,p in enumerate(points):
                    ident=f'B_{cond}_{arm}_L{level}_R{restart}_G{generation}_C{j}'
                    r=execute(entry(cond,arm,ident,spec(level,p),'B',level=level,restart=restart,generation=generation,seed=20261001+1000*ci+100*ai+10*level+restart,
                                    initialization=('baseline','known_hip_leading','diverse_safe')[restart]))
                    if eligible(r,base,arm)[0]:scored.append((r['J_F_task_n_s'],p.copy()))
                scored=sorted(scored+memory,key=lambda x:x[0]);elite=scored[:2]
                if elite:
                    xs=np.array([x[1] for x in elite]);mean=.5*mean+.5*xs.mean(axis=0)
                    std=np.maximum(span*.04,.5*std+.5*xs.std(axis=0));memory=elite
                else:std=np.maximum(span*.04,std*.8)

def collect():
    data=[]
    for p in sorted(PROPOSALS.glob('*.json')):
        e=read(p);rp=RUNS/e['run_id']/'rollout_result.json'
        if rp.exists():data.append((e,read(rp)))
    return data
def persist(status,phase,next_action=None):
    data=collect();count=Counter(r['status'] for _,r in data)
    save(D/'STATE.json',{'status':status,'phase':phase,'updated_utc':stamp(),'completed':len(data),'counts':dict(count),
       'phase_counts':dict(Counter(e['phase'] for e,_ in data)),'elapsed_wall_s':time.time()-read(START_FILE)['epoch'],
       'next_action':next_action,'branch':C['branch'],'no_training':True,'source_commit':C['source_commit']})
    return data

def best_prior(cond,arm):
    b=baseline(cond,arm);best=None;anymatched=None
    for root in (S/'results/coordination_pacing_exploration_v1/runs',S/'results/value_learning_research_v1/runs'):
        for p in root.glob('*/rollout_result.json'):
            try:r=read(p)
            except Exception:continue
            if r.get('condition_id')!=cond or r.get('status')!='VALID':continue
            a=r.get('arm');patt=r.get('pattern') or {}
            if a=='BASELINE':a='NATIVE'
            if a!=arm:continue
            good,iso,res=eligible(r,b,arm)
            row={'path':str(p),'run_id':r['run_id'],'J_F_task_n_s':r['J_F_task_n_s'],'pattern':r.get('pattern'),
                 'isolated':iso,'residual_s':res,'result_sha256':sha(p),'source_commit':r.get('source_commit')}
            if arm=='MATCHED':
                if anymatched is None or row['J_F_task_n_s']<anymatched['J_F_task_n_s']:anymatched=row
            if good and (best is None or row['J_F_task_n_s']<best['J_F_task_n_s']):best=row
    return best,anymatched

def final_comparisons():
    candidates={};all_data=collect()
    for e,r in all_data:
        if e['phase'] not in ('A','B') or e['spec'] is None or r.get('status')!='VALID':continue
        candidates[json.dumps(e['spec'],sort_keys=True)]=e['spec']
    coverage=[]
    for key,p in candidates.items():
        values=[]
        for c in CONDITIONS:
            for arm in ARMS:
                matches=[r for e,r in all_data if e['condition']==c['id'] and e['arm']==arm and e['spec']==p and eligible(r,baseline(c['id'],arm),arm)[0]]
                if matches:values.append(1-min(r['J_F_task_n_s'] for r in matches)/baseline(c['id'],arm)['J_F_task_n_s'])
        coverage.append((len(values),float(np.mean(values)) if values else -1,key))
    winner=max(coverage);fixed=candidates[winner[2]]
    save(D/'FIXED_PATTERN_SELECTION.json',{'descriptor':fixed,'coverage_before_reexecution':winner[0],'mean_fractional_benefit':winner[1],
                                         'selection':'coverage first, mean relative benefit second, in-sample', 'frozen_before_final_cross_execution':True})
    tasks=[]
    for c in CONDITIONS:
        for arm in ARMS:
            ranks=rankable_entries(c['id'],arm);best=ranks[0]
            tasks.append(entry(c['id'],arm,f'F_{c["id"]}_{arm}_confirm',best[1]['spec'],'CONFIRM',discovery_run_id=best[1]['run_id'],expected_J_F=best[0]))
            tasks.append(entry(c['id'],arm,f'F_{c["id"]}_{arm}_fixed',fixed,'FIXED'))
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(execute,tasks))

def analyze():
    data=collect();comparisons=[];entries=[];curve=[];space=[];manifest=[]
    elapsed=time.time()-read(START_FILE)['epoch']
    for c in CONDITIONS:
        case=read(R/c['case_path'])
        for arm in ARMS:
            b=baseline(c['id'],arm);prior,prior_any=best_prior(c['id'],arm)
            ranks=rankable_entries(c['id'],arm);bestcost,beste,bestr=ranks[0]
            confirm=read(RUNS/f'F_{c["id"]}_{arm}_confirm/rollout_result.json')
            confirmation=(confirm['status']=='VALID' and abs(confirm['J_F_task_n_s']-bestcost)<=1e-6)
            fixed=read(RUNS/f'F_{c["id"]}_{arm}_fixed/rollout_result.json')
            oldfixed=read(RUNS/f'A_{c["id"]}_{arm}_fixed_0/rollout_result.json')
            fixedlegal,fixediso,fixedres=eligible(fixed,b,arm)
            previous=prior['J_F_task_n_s'] if prior else b['J_F_task_n_s']
            v2only=bestcost;selected_prior=prior is not None and previous<bestcost
            if selected_prior:
                bestcost=previous;bestpath=Path(prior['path']);bestrecord=read(bestpath);descriptor=prior['pattern'];bestsource='historical_confirmed_or_valid'
            else:bestpath=RUNS/beste['run_id']/'rollout_result.json';bestrecord=bestr;descriptor=beste['spec'];bestsource='v2'
            legal,isolated,residual=eligible(bestrecord,b,arm)
            group=[(e,r) for e,r in data if e['condition']==c['id'] and e['arm']==arm and e['phase'] in ('A','B')]
            inc=previous;local=b['J_F_task_n_s'];perlevel={};restart=[];a_best=previous
            for n,(e,r) in enumerate(group,1):
                ok,iso,res=eligible(r,b,arm)
                if ok:inc=min(inc,r['J_F_task_n_s']);local=min(local,r['J_F_task_n_s'])
                if e['phase']=='A':a_best=inc
                curve.append({'condition':c['id'],'arm':arm,'evaluation':n,'phase':e['phase'],'level':e.get('level'),
                    'restart':e.get('restart'),'generation':e.get('generation'),'run_id':e['run_id'],'status':r['status'],
                    'rankable':ok,'timing_isolated':iso,'candidate_J_F_n_s':r.get('J_F_task_n_s'),'best_J_F_n_s':inc,
                    'v2_only_best_J_F_n_s':local,'prior_incumbent_J_F_n_s':previous})
            for level in (1,2,3):
                xs=[(e,r) for e,r in group if e['phase']=='B' and e['level']==level]
                good=[r['J_F_task_n_s'] for e,r in xs if eligible(r,b,arm)[0]]
                perlevel[str(level)]=min(good) if good else None
                for rr in range(3):
                    rs=[(e,r) for e,r in xs if e['restart']==rr];costs=[r['J_F_task_n_s'] for e,r in rs if eligible(r,b,arm)[0]]
                    restart.append({'level':level,'restart':rr,'initialization':('baseline','known_hip_leading','diverse_safe')[rr],
                                    'evaluations':len(rs),'best_J_F':min(costs) if costs else None})
                space.append({'condition':c['id'],'arm':arm,'level':level,'dimension':DIMENSIONS[level],
                              'evaluations':len(xs),'rankable_count':len(good),'best_level_J_F':perlevel[str(level)]})
            cp=c.get('checkpoint_rep')
            human={'case_sha256':c['case_sha256'],'case_model_configuration':case.get('research_model',case.get('human',{})),
                   'physical_case_file':c['case_path'],'checkpoint_rep':cp,'source_checkpoint_sha256':bestrecord.get('source_checkpoint_sha256'),
                   'allowed_online_model':'receipt-owned deployable estimated state/belief; hidden case physics for plant and reproduction only'}
            metrics={k:bestrecord.get(k) for k in ('mean_force_n','rms_force_n','peak_force_n','moment_integral_nm_s','moment_peak_nm',
                        'minimum_clearance_m','duration_s','outbound_duration_s','return_duration_s','dq_rms_rad_s','ddq_rms_rad_s2')}
            ent={'condition':c['id'],'physical_condition_id':c['physical_condition_id'],'adaptation_state':c['adaptation_state'],
                 'initial_state':{'task_start_deg':case['task']['start_deg'],'task_goal_deg':case['task']['goal_deg'],'checkpoint_rep':cp,
                                  'boundary_before_J_F_n_s':bestrecord.get('boundary_before_J_F_n_s'),'trace_file_role':'exact full initial state available in manifested trace and frozen checkpoint'},
                 'Human_model_state':human,'coordination_parameters':descriptor,'trajectory_descriptor':{'planned_segments':bestrecord.get('planned_segments'),
                    'nominal_template_run_id':c['baseline_run_id'],'semantics':'scheduler-screened targets; no replay of evaluation-only actual trajectory'},
                 'J_F_n_s':bestcost,'force_metrics':metrics,'clearance_m':metrics['minimum_clearance_m'],'duration_s':metrics['duration_s'],
                 'matched_native_label':arm,'timing_isolated':isolated if arm=='MATCHED' else False,'phase_timing_residual_s':residual,
                 'source_commit':bestrecord.get('source_commit'),'result_path':str(bestpath.relative_to(R)),'manifest_hash':sha(bestpath),
                 'manifest_hash_semantics':'SHA256 of immutable rollout result containing raw-file hashes; avoids cyclic database/manifest digest',
                 'reference_source':bestsource,'v2_confirmation_pass':confirmation if bestsource=='v2' else None}
            entries.append(ent)
            comparisons.append({'condition':c['id'],'arm':arm,'baseline_J_F_n_s':b['J_F_task_n_s'],'prior_best_J_F_n_s':previous,
                'prior_all_valid_matched':prior_any,'v2_best_J_F_n_s':v2only,'best_known_J_F_n_s':bestcost,
                'benefit_n_s':b['J_F_task_n_s']-bestcost,'benefit_percent':100*(1-bestcost/b['J_F_task_n_s']),
                'gain_over_prior_n_s':previous-bestcost,'gain_after_phase_A_n_s':a_best-min(previous,v2only),
                'search_baseline_confirmation_pass':confirmation,'rankable_v2_best_run_id':beste['run_id'],
                'fixed_prior_J_F':oldfixed.get('J_F_task_n_s'),'fixed_best_J_F':fixed.get('J_F_task_n_s'),
                'fixed_best_rankable':fixedlegal,'fixed_best_timing_isolated':fixediso,'fixed_best_residual_s':fixedres,
                'fixed_vs_best_gap_n_s':fixed['J_F_task_n_s']-bestcost if fixedlegal else None,
                'best_by_level':perlevel,'restarts':restart,'evaluations':len(group),'timing_isolated':isolated})
    for e,r in data:
        out=RUNS/e['run_id'];files={}
        for name in ('rollout_result.json','process_log.json'):
            if (out/name).exists():files[name]=sha(out/name)
        for item in r.get('raw_storage',{}).values():files[item['stored_path']]=item['stored_sha256']
        manifest.append({'run_id':e['run_id'],'status':r['status'],'proposal_sha256':sha(PROPOSALS/(e['run_id']+'.json')),'files':files,
                         'original_raw_hashes':r.get('raw_files_sha256',{})})
    save(D/'BEST_KNOWN_REFERENCE_DATABASE.json',{'schema':'best_known_reference_database_v2','entries':entries,
         'reference_scope':'five development conditions, frozen initial/adaptation states; MATCHED isolated and NATIVE separate','no_global_optimum':True,'no_RL_training':True})
    save(D/'CONDITION_COMPARISON.json',{'rows':comparisons,'all_in_sample':True,'cross_arm_cost_comparisons_not_coordination_effects':True})
    save(D/'PARAMETER_SPACE_ANALYSIS.json',{'rows':space,'dimensions':DIMENSIONS,'restart_results':comparisons,
          'interpretation':'Independent level minima and nested running envelopes are different; small populations/two generations limit convergence. Shared peak/width are irrelevant when all amplitudes zero; smooth bases can be correlated.'})
    with (D/'SEARCH_CONVERGENCE.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(curve[0]));writer.writeheader();writer.writerows(curve)
    save(D/'RAW_DATA_MANIFEST.json',{'schema':'best_known_raw_manifest_v2','rollouts':manifest,'historical_reference_results':
        [{'path':e['result_path'],'sha256':e['manifest_hash']} for e in entries if e['reference_source']!='v2'],
        'source_fingerprints_sha256':sha(D/'SOURCE_FINGERPRINTS.json'),'contract_sha256':sha(D/'SEARCH_CONTRACT.json')})
    timings=[r['elapsed_host_s'] for _,r in data if r.get('elapsed_host_s') is not None]
    save(D/'RUNTIME.json',{'total_wall_s':elapsed,'sum_rollout_host_s':sum(timings),'mean_rollout_s':float(np.mean(timings)),
        'median_rollout_s':float(np.median(timings)),'parallel_simulations':2,'per_condition_arm':[
          {'condition':c['id'],'arm':arm,'mean_s':float(np.mean([r['elapsed_host_s'] for e,r in data if e['condition']==c['id'] and e['arm']==arm and 'elapsed_host_s' in r]))}
          for c in CONDITIONS for arm in ARMS]})
    table=['|Condition|Arm|Baseline J_F|Best-known J_F|Benefit N·s|Benefit %|Gain over prior|Fixed-best gap|',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for x in comparisons:table.append(f'|{x["condition"]}|{x["arm"]}|{x["baseline_J_F_n_s"]:.6f}|{x["best_known_J_F_n_s"]:.6f}|{x["benefit_n_s"]:.6f}|{x["benefit_percent"]:.3f}|{x["gain_over_prior_n_s"]:.6f}|{x["fixed_vs_best_gap_n_s"] if x["fixed_vs_best_gap_n_s"] is not None else "infeasible/confounded"}|')
    (D/'FIXED_VS_SEARCH_BASELINE.md').write_text('# Fixed versus search baseline\n\n'+ '\n'.join(table)+'\n\nOriginal baseline, preregistered fixed hip-leading and post-search coverage-selected fixed are recorded in CONDITION_COMPARISON.json. Missing/infeasible/timing-confounded fixed results count against applicability. This is an in-sample teacher comparison. No general fixed-policy sufficiency or personalization claim follows from a best-of-search table.\n')
    matched=[x for x in comparisons if x['arm']=='MATCHED'];native=[x for x in comparisons if x['arm']=='NATIVE']
    more_budget=[x for x in comparisons if x['gain_after_phase_A_n_s']>1e-6]
    freedom=[x for x in comparisons if x['best_by_level']['1'] is not None and min(v for v in x['best_by_level'].values() if v is not None)<x['best_by_level']['1']-1e-6]
    report=['# Best-Known Coordination Reference Search v2','',
      'Finite-budget teacher generation complete. No RL or value model was trained. Original source, controller, Human dynamics, safety thresholds, planner objective and Scientific Mode remain fingerprint-identical.',
      '',*table,'',
      f'Executed {len(data)} rollouts: '+str(dict(Counter(r['status'] for _,r in data)))+'. Phase A 60, CEM Phase B 540, confirmation/fixed comparison 20. Signed hip/knee, width/catch-up, per-phase offsets and smooth control coefficients have dimensions 6/12/20. Each of three initializations has two generations of three candidates. This sparse finite envelope does not establish convergence.',
      '',f'Wall time {elapsed/3600:.3f} h; mean rollout {np.mean(timings):.3f} s, median {np.median(timings):.3f} s; two concurrent simulations. Runtime includes offline search, not online latency optimization.',
      '', '## Direct answers','',
      '1. Absolute best-known J_F is condition/arm specific; use the table. Comparing minima across different tasks is not meaningful.',
      '2. Baseline improvements and percentages are in the table; MATCHED and NATIVE have separate baselines.',
      '3. Additional Phase B budget improved '+str(len(more_budget))+' of 10 condition-arm rows relative to the prior+Phase-A incumbent. This is observed headroom, not an extrapolated limit.',
      '4. Independent L2/L3 minima improve over L1 in '+str(len(freedom))+' of 10 rows; inspect per-level sample counts and restart spread. Extra dimensions with no improvement do not prove the family exhausted.',
      '5. No universal optimum is established. The exact common fixed descriptor, coverage and condition-specific gaps are in FIXED_PATTERN_SELECTION.json and FIXED_VS_SEARCH_BASELINE.md.',
      '6. Condition-specific best parameters and feasibility differ; this supports condition-conditioned teacher targets, but it does not establish that a learned personalized policy beats a prospective fixed comparator.',
      '7. The historical 40.627960 N·s is an improvement in sync_120 matched scheduling. Current sync/variable isolated improvements are '+str([(x['condition'],x['benefit_n_s']) for x in matched if x['condition'] in ('sync_120','variable_start_120')])+'. There is no certified lower bound, so its distance to a search/global limit cannot be quantified. Budget/freedom gains and initialization disagreement mean saturation cannot be claimed.',
      '8. Learn a low-dimensional coordination/chunk parameter action with phase, remaining progress and explicit pacing context, through the existing safety scheduler. A single next waypoint cannot describe lead duration/catch-up and OUTBOUND/RETURN asymmetry.',
      '9. Larger RL complexity is not justified by this teacher search alone. First test fixed versus condition-indexed lookup and a simple supervised value/ranking learner on fresh supported starts; no learner is trained here.',
      '', '## Learning readiness','',
      'State: deployable q/dq estimate and receipt-owned reference; phase/progress, start/goal/remaining ROM, previous declared chunk, estimated Human dynamics/geometry belief and confidence/residual/sample history, causal adaptation state, scheduler/governor and pacing context. Frozen physical condition ids and simulation Human truth are reproduction metadata, not deployable features.',
      'Action: signed hip lead/knee lag, lead peak/width, phase offsets and optional smooth basis coefficients. Target: full remaining-task absolute J_F conditioned on declared continuation and timing; paired delta J against same-state/same-arm baseline is useful for ranking. Keep moment/clearance/intensity as separate constrained diagnostics, not a mixed reward. Full-task outcome cannot be replaced by first-waypoint force.',
      '', '## Limits and evidence','',
      'All five conditions were previously used and are in-sample teacher-generation conditions, not fresh held-out patients. low_ordinary_early is an adaptation checkpoint of one session. Deterministic baseline/replay/confirmation is reproducibility, not independent subjects. MATCHED physically valid timing-confounded outcomes remain in raw results and are excluded from isolated ranking. NATIVE effects may include timing. Initializations with infeasible candidates are retained.',
      'Database entries may retain a stronger historical VALID reference. Such entries are separately sourced and never represented as a new v2 CEM discovery. Prior all-valid timing-confounded matched minima are preserved in CONDITION_COMPARISON.json, separate from isolated references.',
      'CEM design context: [Pinneri et al., 2021](https://proceedings.mlr.press/v155/pinneri21a.html); smoothed diagonal CEM/elite memory used here, not a full iCEM implementation or a convergence guarantee.',
      'RAW_DATA_MANIFEST.json records stored and original content hashes; raw JSON is losslessly compressed. Database manifest_hash is the rollout-result digest containing raw hashes. SEARCH_CONVERGENCE.csv includes new-only and prior-incumbent envelopes. Source fingerprints and contract fix all production/config/scientific semantics.']
    (D/'BEST_KNOWN_REFERENCE_SEARCH_REPORT.md').write_text('\n'.join(report)+'\n')
    checks={'protected_fingerprint_count':check_frozen(),'baseline_gate':read(D/'PHASE_A_GATE.json')['status'],
            'new_reference_confirmation_all_pass':all(x['search_baseline_confirmation_pass'] for x in comparisons),
            'required_outputs_present':all((D/n).exists() for n in ['BEST_KNOWN_REFERENCE_SEARCH_REPORT.md','BEST_KNOWN_REFERENCE_DATABASE.json','SEARCH_CONVERGENCE.csv','PARAMETER_SPACE_ANALYSIS.json','CONDITION_COMPARISON.json','FIXED_VS_SEARCH_BASELINE.md','RAW_DATA_MANIFEST.json','STATE.json']),
            'parameter_checks':test_space(),'no_training':True}
    save(D/'FINAL_VERIFICATION.json',checks)
    if not checks['new_reference_confirmation_all_pass']:raise RuntimeError('REFERENCE_CONFIRMATION_FAILED')
    persist('COMPLETE_FINITE_BUDGET','FINAL_ANALYSIS','stop; no RL training')
    print(json.dumps({'complete':True,'comparisons':[{k:x[k] for k in ('condition','arm','best_known_J_F_n_s','benefit_n_s','gain_over_prior_n_s')} for x in comparisons]}),flush=True)

def main():
    if not START_FILE.exists():save(START_FILE,{'epoch':time.time(),'utc':stamp()})
    check_frozen();pairs=[(ci,ai) for ci in range(len(CONDITIONS)) for ai in range(2)]
    try:
        persist('RUNNING','PHASE_A','baseline and safe proposal qualification')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(phase_a_pair,pairs))
        gate=gate_a()
        if gate['status']!='PASS':raise RuntimeError('PHASE_A_GATE_FAILED')
        persist('RUNNING','PHASE_B','nested CEM with three initialization families')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(search_pair,pairs))
        check_frozen();persist('SEARCH_COMPLETE','CONFIRMATION','rerun per-row best and one fixed descriptor')
        subprocess.run(['git','-C',str(R),'add','--',str(D.relative_to(R))],check=True)
        subprocess.run(['git','-C',str(R),'add','-f','--',str(PROPOSALS.relative_to(R)),str(START_FILE.relative_to(R))],check=True)
        subprocess.run(['git','-C',str(R),'commit','-m','Complete bounded v2 coordination CEM search and preserve raw evidence'],check=True)
        final_comparisons();analyze()
    except BaseException as error:
        save(D/'STOP_RECORD.json',{'utc':stamp(),'error':str(error),'traceback':traceback.format_exc()})
        persist('STOPPED_WITH_EVIDENCE','CHECKPOINT',str(error));raise
if __name__=='__main__':main()
