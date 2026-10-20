"""Offline attempt/native accounting and immutable-history verification."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,collections,shutil,traceback
import argparse,ast,gzip,math,re
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
sys.dont_write_bytecode=True
DT=.00025
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*2**20),b''):h.update(block)
    return h.hexdigest()
def read(n,default=None):
    f=P/n;return json.loads(f.read_text()) if f.exists() else default
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def array_items(path,key):
    """Stream one named JSON array without importing simulator/runtime modules.

    Unlike the historical reader, an absent or truncated array is an error,
    never an empty array which could accidentally prove a zero-step run.
    """
    opener=gzip.open if str(path).endswith('.gz') else open
    decoder=json.JSONDecoder();pattern=re.compile(re.escape(json.dumps(key))+r'\s*:\s*\[')
    with opener(path,'rt',encoding='utf-8') as stream:
        buf='';eof=False
        while True:
            block=stream.read(2**18);eof=not block;buf+=block;match=pattern.search(buf)
            if match:buf=buf[match.end():];break
            if eof:raise ValueError('MISSING_ARRAY:'+key)
            buf=buf[-(len(key)+128):]
        first=True
        while True:
            buf=buf.lstrip()
            while not buf and not eof:
                block=stream.read(2**18);eof=not block;buf+=block;buf=buf.lstrip()
            if not buf:raise ValueError('TRUNCATED_ARRAY:'+key)
            if buf[0]==']':return
            if not first:
                if buf[0]!=',':raise ValueError('MISSING_ARRAY_SEPARATOR:'+key)
                buf=buf[1:].lstrip()
            while True:
                try:item,end=decoder.raw_decode(buf);break
                except json.JSONDecodeError:
                    if eof:raise ValueError('TRUNCATED_OR_MALFORMED_ARRAY:'+key)
                    block=stream.read(2**18);eof=not block;buf+=block
                    buf=buf.lstrip()
            yield item
            buf=buf[end:];first=False

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def steps(value):
    return int(value) if number(value) and value>=0 and int(value)==value else None

def clock_steps(value):
    if not number(value) or value<0:return None
    rounded=round(value/DT)
    return rounded if abs(value-rounded*DT)<1e-7 else None

def accounting(package=None,write=True):
    """Audit saved evidence only. Null totals mean incomplete evidence, not zero."""
    root=Path(package) if package is not None else P
    now=time.time();errors=[];unknown=[];read_errors=[]
    def load(name,default=None):
        path=root/name
        if not path.exists():return default
        try:return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError) as error:
            read_errors.append(dict(path=str(path),error=str(error)));return default
    def artifact(path):
        if not path.exists():return None
        stat=path.stat()
        return dict(path=str(path),sha256=sha(path),size=stat.st_size,mtime_ns=stat.st_mtime_ns)
    ledger=root/'ATTEMPTS.jsonl';events=[]
    ledger_before=ledger.stat() if ledger.exists() else None
    if ledger.exists():
        for i,line in enumerate(ledger.read_text(encoding='utf-8-sig').splitlines(),1):
            if not line.strip():continue
            try:
                event=json.loads(line)
                if not isinstance(event,dict) or not isinstance(event.get('id'),str) or event.get('event') not in ['START','END']:raise ValueError('INVALID_EVENT')
                events.append(event)
            except ValueError as error:errors.append(dict(code='MALFORMED_LEDGER_LINE',line=i,error=str(error)))
    else:unknown.append('MISSING_ATTEMPT_LEDGER')
    starts=[x for x in events if x['event']=='START'];ends=[x for x in events if x['event']=='END']
    bystart=collections.defaultdict(list);byend=collections.defaultdict(list)
    for event in starts:bystart[event['id']].append(event)
    for event in ends:byend[event['id']].append(event)
    duplicate_starts={k:len(v) for k,v in bystart.items() if len(v)!=1}
    duplicate_ends={k:len(v) for k,v in byend.items() if len(v)!=1}
    orphan_ends=sorted(set(byend)-set(bystart));open_ids=sorted(set(bystart)-set(byend))
    for code,value in [('DUPLICATE_START_IDS',duplicate_starts),('DUPLICATE_END_IDS',duplicate_ends),('ORPHAN_END_IDS',orphan_ends)]:
        if value:errors.append(dict(code=code,value=value))
    for path in (root/'source/results').glob('*/runtime_artifacts.json*'):
        if path.parent.name not in bystart:errors.append(dict(code='RAW_ARTIFACT_WITHOUT_START',path=str(path)))
    plan=load('RUN_PLAN.json',{});registered_budget=steps(plan.get('physics_budget'))
    budget=min(80,registered_budget) if registered_budget is not None else None
    if registered_budget is not None and registered_budget>80:errors.append(dict(code='REGISTERED_BUDGET_EXCEEDS_STUDY_CAP',registered=registered_budget,cap=80))
    if budget is None:unknown.append('MISSING_OR_INVALID_PHYSICS_BUDGET')
    elif len(starts)>budget:errors.append(dict(code='START_BUDGET_EXCEEDED',observed=len(starts),limit=budget))
    deadlines=[plan.get(k) for k in ['dispatch_cutoff_unix','no_new_physics_after_unix'] if number(plan.get(k))]
    cutoff=min(deadlines) if deadlines else None;timeout=plan.get('physical_timeout_s')
    margin_cutoff=cutoff-timeout if cutoff is not None and number(timeout) else None
    if cutoff is None:unknown.append('MISSING_DISPATCH_DEADLINE')
    for event in starts:
        if not number(event.get('unix')):errors.append(dict(code='INVALID_START_CLOCK',id=event['id']))
        elif cutoff is not None and event['unix']>=cutoff:errors.append(dict(code='START_AFTER_DISPATCH_CUTOFF',id=event['id']))
        elif margin_cutoff is not None and event['unix']>=margin_cutoff:errors.append(dict(code='START_VIOLATES_FROZEN_TIMEOUT_MARGIN',id=event['id']))
    records=[]
    # One evidence record per unique attempt, with every duplicated event retained.
    for ident,start_events in bystart.items():
        start=start_events[0];end=byend.get(ident,[]);closed=len(start_events)==len(end)==1
        pid=start.get('patient_id');is_parent=ident.endswith('_parent')
        re=[];ru=[];data=load('output/'+ident+'_DATA.json',{});partial=load('output/'+ident+'_PARTIAL_COMPUTE.json',{})
        metric=data.get('metric') or load('output/'+ident+'.json',{})
        summary=load('source/results/'+ident+'/summary.json',{})
        if not isinstance(pid,str):ru.append('MISSING_PATIENT_ID')
        wall=None
        if closed:
            if number(start.get('unix')) and number(end[0].get('unix')):
                wall=end[0]['unix']-start['unix']
                if wall<0:re.append('END_BEFORE_START')
            else:re.append('INVALID_END_CLOCK')
            if end[0].get('joined') is not True:ru.append('END_JOIN_NOT_VERIFIED')
        raw=root/'source/results'/ident/'runtime_artifacts.json.gz'
        if not raw.exists() and raw.with_suffix('').exists():raw=raw.with_suffix('')
        native_count=receipt_steps=first=last=None;raw_error=None;native_evidence=None
        receipt_count=None;stage_counts=None
        if raw.exists():
            before=raw.stat()
            try:
                native_count=0;previous=None
                for row in array_items(raw,'native_states_evaluation_only'):
                    stamp=row.get('time_s')
                    if not number(stamp):raise ValueError('INVALID_NATIVE_CLOCK')
                    if previous is not None and abs(stamp-previous-DT)>1e-7:raise ValueError('NONCONTIGUOUS_NATIVE_CLOCK')
                    native_count+=1
                    if first is None:first=stamp
                    previous=last=stamp
                receipt_steps=receipt_count=0;receipt_last=None
                for row in array_items(raw,'command_receipts'):
                    if not row.get('applied'):continue
                    count=steps(row.get('native_steps'))
                    if count is None:raise ValueError('INVALID_APPLIED_RECEIPT_STEPS')
                    receipt_count+=1;receipt_steps+=count
                    a=row.get('start_physics_s');b=row.get('end_physics_s')
                    if number(a) and number(b):
                        if abs(b-a-count*DT)>1e-7:raise ValueError('RECEIPT_INTERVAL_STEP_MISMATCH')
                        if receipt_last is not None and abs(a-receipt_last)>1e-7:raise ValueError('NONCONTIGUOUS_RECEIPT_INTERVALS')
                        receipt_last=b
                after=raw.stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('RAW_ARTIFACT_CHANGED_DURING_AUDIT')
                if native_count!=receipt_steps:re.append('NATIVE_RECEIPT_COUNT_MISMATCH')
                if native_count and clock_steps(last)!=native_count:re.append('NATIVE_TOTAL_CLOCK_COUNT_MISMATCH')
                native_evidence=artifact(raw)
                final_stat=raw.stat()
                if (before.st_size,before.st_mtime_ns)!=(final_stat.st_size,final_stat.st_mtime_ns):raise ValueError('RAW_ARTIFACT_CHANGED_DURING_HASH')
            except (OSError,ValueError,KeyError,TypeError) as error:
                raw_error=str(error)
                (re if closed else ru).append('RAW_EVIDENCE_ERROR:'+str(error))
                native_count=receipt_steps=None
        else:ru.append('MISSING_RAW_NATIVE_AND_RECEIPT_EVIDENCE')
        inherited_candidates={}
        if is_parent:inherited_candidates['cold_parent']=0
        else:
            child=data.get('child') or {}
            if child.get('physics_step_at_fork') is not None:
                count=steps(child['physics_step_at_fork'])
                if count is None:re.append('INVALID_CHILD_INHERITED_COUNTER')
                else:inherited_candidates['DATA.child.physics_step_at_fork']=count
            for label,source in [('metric',metric),('partial',partial)]:
                total=steps(source.get('native_physics_steps'))
                if total is None:total=clock_steps(source.get('simulation_seconds'))
                delta=steps(source.get('actual_new_native_physics_steps'))
                if total is not None and delta is not None:
                    if total<delta:re.append('NEGATIVE_INHERITED_COUNTER:'+label)
                    else:inherited_candidates[label+'.total_minus_actual_new']=total-delta
            snapshot=load('reports/'+ident+'_SNAPSHOT.json',{})
            if start.get('snapshot_hash') and snapshot.get('hash')==start['snapshot_hash']:
                count=clock_steps((snapshot.get('manifest') or {}).get('task_last_physics_time'))
                if count is not None:inherited_candidates['verified_snapshot.manifest.task_last_physics_time/DT']=count
        if len(set(inherited_candidates.values()))>1:re.append('INHERITED_COUNTER_SOURCES_DISAGREE')
        inherited=next(iter(inherited_candidates.values())) if inherited_candidates and len(set(inherited_candidates.values()))==1 else None
        if inherited is None:ru.append('INHERITED_PREFIX_NOT_VERIFIED')
        actual=None
        if native_count is not None and inherited is not None:
            actual=native_count-inherited
            if actual<0:re.append('NEGATIVE_ACTUAL_NEW_NATIVE_STEPS');actual=None
        for label,source in [('metric',metric),('partial',partial)]:
            for key,expected in [('native_physics_steps',native_count),('actual_new_native_physics_steps',actual)]:
                if key in source:
                    counter=steps(source[key])
                    if counter is None:re.append('INVALID_COUNTER:'+label+'.'+key)
                    elif expected is not None and counter!=expected:re.append('COUNTER_MISMATCH:'+label+'.'+key)
            for key,expected in [('simulation_seconds',native_count),('actual_new_simulation_seconds',actual)]:
                if key in source:
                    counter=clock_steps(source[key])
                    if counter is None:re.append('INVALID_CLOCK_COUNTER:'+label+'.'+key)
                    elif expected is not None and counter!=expected:re.append('CLOCK_COUNTER_MISMATCH:'+label+'.'+key)
        # A partial metric is a declared count, not independently verified physics.
        declared_partial=steps(partial.get('actual_new_native_physics_steps'))
        record=dict(id=ident,patient_id=pid,kind=start.get('kind'),START=start,START_events=start_events,END=end,closed=closed,wall_seconds=wall,
            archived_native_rows=native_count,applied_receipt_native_steps=receipt_steps,applied_receipt_count=receipt_count,
            inherited_prefix_native_steps=inherited,inherited_counter_sources=inherited_candidates,
            actual_new_native_steps=actual,native_count_match=None if native_count is None or receipt_steps is None else native_count==receipt_steps,
            first_native_s=first,last_native_s=last,actual_new_simulation_seconds=None if actual is None else actual*DT,
            task_complete=summary.get('status')=='COMPLETE',metric_actual_new_steps=metric.get('actual_new_native_physics_steps'),
            partial_declared_actual_new_steps=declared_partial,partial_compute=partial or None,artifact_error=raw_error,raw_artifact=native_evidence,
            errors=re,unknown_evidence=ru)
        if is_parent:
            boundary=load('audit/'+str(pid)+'_FORK_CONTEXT.json',{})
            pretask=boundary.get('physical_s',0)-boundary.get('task_s',0) if boundary else None
            record.update(commissioning_and_legal_prefix_native_steps=clock_steps(boundary.get('physical_s')),
                task_start_physics_s=pretask,pre_task_native_steps=clock_steps(pretask),commissioning_native_steps=None,
                pre_task_note='Pre-task includes commissioning and any ACTIVE_RECOVERY; never equated with commissioning alone.')
            trace=root/'source/results'/ident/'trace.npz'
            if trace.exists():
                try:
                    import numpy as np
                    with np.load(trace,allow_pickle=False) as z:
                        times=z['time_s'];stages=z['stage'];spans=[]
                        for i in range(len(stages)):
                            label=str(stages[i])
                            if i==0 or label!=str(stages[i-1]):spans.append(dict(stage=label,start_s=float(times[i])))
                        for i,span in enumerate(spans):
                            span['end_s']=spans[i+1]['start_s'] if i+1<len(spans) else last
                            span['native_steps']=clock_steps(span['end_s']-span['start_s']) if span['end_s'] is not None else None
                            span['closed_by_stage_transition']=i+1<len(spans)
                        record['stage_time_intervals_from_trace']=spans
                        commissioning=[x for x in spans if x['stage']=='COMMISSIONING']
                        if commissioning and all(x['closed_by_stage_transition'] and x['native_steps'] is not None for x in commissioning):
                            record['commissioning_native_steps']=sum(x['native_steps'] for x in commissioning)
                            record['commissioning_count_basis']='Native-clock-aligned trace stage boundaries; not trace row count.'
                except (ImportError,OSError,ValueError,KeyError) as error:record['stage_interval_error']=str(error)
        record['status']='FAIL' if re else 'IN_PROGRESS' if not closed else 'UNKNOWN' if ru else 'PASS'
        records.append(record)
    serial=serial_evidence(root,records,load,artifact,now)
    ledger_after=ledger.stat() if ledger.exists() else None
    ledger_stable=ledger_before is not None and ledger_after is not None and (ledger_before.st_size,ledger_before.st_mtime_ns)==(ledger_after.st_size,ledger_after.st_mtime_ns)
    if not ledger_stable:unknown.append('LEDGER_MISSING_OR_CHANGED_DURING_AUDIT')
    if serial['status']=='FAIL':errors.append(dict(code='SERIAL_EVIDENCE_FAILURE',details=serial['errors']))
    elif serial['status']!='PASS':unknown.append('SERIAL_EXECUTION_NOT_FULLY_VERIFIED')
    if read_errors:unknown.append('UNREADABLE_JSON_EVIDENCE')
    if any(r['status']=='FAIL' for r in records):errors.append(dict(code='ATTEMPT_EVIDENCE_FAILURE',ids=[r['id'] for r in records if r['status']=='FAIL']))
    if any(r['unknown_evidence'] for r in records):unknown.append('ATTEMPT_EVIDENCE_INCOMPLETE')
    unresolved=[r['id'] for r in records if r['actual_new_native_steps'] is None or r['errors']]
    known=[r for r in records if r['actual_new_native_steps'] is not None and not r['errors']]
    subtotal=sum(r['actual_new_native_steps'] for r in known)
    complete_counts=ledger_stable and not open_ids and not unresolved and not duplicate_starts and not orphan_ends and not duplicate_ends and not read_errors and not any(e['code'] in ['MALFORMED_LEDGER_LINE','RAW_ARTIFACT_WITHOUT_START'] for e in errors)
    total=subtotal if complete_counts else None
    static=load('STATIC_PATIENT_AUDIT.json',{});cohort=load('VIRTUAL_PATIENT_COHORT.json',{})
    result=dict(status='FAIL' if errors else 'IN_PROGRESS' if open_ids or (ledger_before is not None and not ledger_stable) else 'UNKNOWN' if unknown else 'PASS',
        START_count=len(starts),unique_START_ids=len(bystart),END_count=len(ends),max_START=budget,
        registered_physics_budget=registered_budget,study_START_cap=80,ledger_snapshot_stable_during_audit=ledger_stable,
        duplicate_START_ids=duplicate_starts,duplicate_END_ids=duplicate_ends,orphan_END_ids=orphan_ends,unclosed_START_ids=open_ids,
        budget_status='UNKNOWN' if budget is None else 'PASS' if len(starts)<=budget else 'FAIL',
        dispatch_cutoff_unix=cutoff,frozen_dispatch_margin_cutoff_unix=margin_cutoff,
        all_physics_serial=True if serial['status']=='PASS' else False if serial['status']=='FAIL' else None,serial_evidence=serial,
        actual_new_native_steps=total,actual_new_simulation_seconds=None if total is None else total*DT,
        known_verified_native_steps_subtotal=subtotal,known_verified_simulation_seconds_subtotal=subtotal*DT,
        unresolved_count_attempt_ids=unresolved,records=records,errors=errors,unknown_evidence=unknown,read_errors=read_errors,
        model_generation_and_static_checks=dict(registered_models=len(cohort.get('patients',[])),static_audit_records=len(static.get('records',[])),
            static_native_steps=0,static_note='Model generation/static checks are excluded from physical START accounting; no simulator is imported by this audit.'),
        wall_note='Parent wall spans include child wait time. Parent physics is counted once; every child subtracts its verified inherited prefix. Never sum overlapping parent and child wall durations.',
        physics_started_by_accounting=0,training_performed=False,updated_unix=now)
    if write:
        path=root/'ATTEMPT_ACCOUNTING.json';tmp=path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)
    print('ACCOUNTING',result['status'],len(starts),total,'known_subtotal',subtotal,flush=True)
    return result

def serial_evidence(root,records,load,artifact,now):
    """Observed owner/arm nonoverlap + immutable blocking-wait implementation."""
    errors=[];unknown=[];owners=[];checks=[];source=[]
    manifest=load('EXECUTION_CODE_MANIFEST.json',{});expected=manifest.get('files',{})
    manifest_file=root/'EXECUTION_CODE_MANIFEST.json';manifest_hash=sha(manifest_file) if manifest_file.exists() else None
    for rel,required in [('serial_campaign.py','wait'),('code/matched_harness.py','waitpid'),('cross_runner.py',None)]:
        path=root/rel;entry=artifact(path)
        if entry is None or rel not in expected:unknown.append('MISSING_FROZEN_SERIAL_SOURCE:'+rel);continue
        entry.update(expected_sha256=expected[rel],matches_frozen=entry['sha256']==expected[rel])
        if not entry['matches_frozen']:errors.append('SERIAL_SOURCE_CHANGED:'+rel)
        if required:
            try:
                tree=ast.parse(path.read_text(encoding='utf-8-sig'))
                calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr==required]
                if required=='waitpid':calls=[n for n in calls if len(n.args)>=2 and isinstance(n.args[1],ast.Constant) and n.args[1].value==0]
                entry['blocking_wait_call_lines']=[n.lineno for n in calls]
                if not calls:errors.append('BLOCKING_WAIT_NOT_FOUND:'+rel)
            except (SyntaxError,ValueError) as error:errors.append('SERIAL_SOURCE_PARSE:'+str(error))
        source.append(entry)
    active=load('OWNED_ACTIVE_PROCESS.json',{})
    pids=sorted({r['patient_id'] for r in records if isinstance(r['patient_id'],str)})
    for pid in pids:
        owner=load('audit/'+pid+'_OWNER.json',{})
        if not owner and active.get('patient_id')==pid:owner=active
        if not owner:unknown.append('MISSING_OWNER_INTERVAL:'+pid);continue
        owner=dict(owner);owner['complete']=number(owner.get('end_unix')) and owner.get('joined') is True
        if not number(owner.get('start_unix')):errors.append('INVALID_OWNER_START:'+pid);continue
        bound=owner.get('end_unix') if number(owner.get('end_unix')) else now
        if bound<owner['start_unix']:errors.append('NEGATIVE_OWNER_INTERVAL:'+pid)
        if not owner['complete']:unknown.append('UNFINISHED_OWNER_INTERVAL:'+pid)
        owner['audit_interval_end_unix']=bound;owners.append(owner)
        patient_records=[r for r in records if r['patient_id']==pid]
        for record in patient_records:
            stamp=record['START'].get('unix')
            if number(stamp) and not owner['start_unix']<=stamp<=bound:errors.append('START_OUTSIDE_OWNER:'+record['id'])
            for end in record['END']:
                if number(end.get('unix')) and not owner['start_unix']<=end['unix']<=bound:errors.append('END_OUTSIDE_OWNER:'+record['id'])
            captured=record['START'].get('source_sha256')
            if captured is None:unknown.append('MISSING_START_SOURCE_HASH:'+record['id'])
            elif captured!=manifest_hash:errors.append('START_FROZEN_MANIFEST_MISMATCH:'+record['id'])
        arms=[r for r in patient_records if not r['id'].endswith('_parent')]
        parents=[r for r in patient_records if r['id'].endswith('_parent')]
        if len(parents)!=1:unknown.append('UNIQUE_PATIENT_PARENT_NOT_VERIFIED:'+pid)
        parent_checks=load('reports/'+pid+'_PARENT_CHECKS.json',[])
        intervals=[]
        for arm in arms:
            a=arm['START'].get('unix');b=arm['END'][0].get('unix') if arm['closed'] else now
            if number(a) and number(b):intervals.append(dict(id=arm['id'],start_unix=a,end_unix=b,closed=arm['closed']))
            if len(parents)==1:
                parent=parents[0];pa=parent['START'].get('unix');pb=parent['END'][0].get('unix') if parent['closed'] else now
                if all(number(x) for x in [a,b,pa,pb]) and not pa<=a<=b<=pb:errors.append('ARM_OUTSIDE_PARENT_SPAN:'+arm['id'])
            relevant=[c for c in parent_checks if c.get('id')==arm['id']]
            check=dict(id=arm['id'],checks=relevant,closed=arm['closed'])
            if arm['closed']:
                if len(relevant)!=1:unknown.append('UNIQUE_PARENT_HASH_CHECK_MISSING:'+arm['id'])
                else:
                    c=relevant[0];snapshot=arm['START'].get('snapshot_hash')
                    check['verified']=bool(snapshot) and c.get('unchanged') is True and c.get('before')==c.get('after')==snapshot
                    if not check['verified']:errors.append('PARENT_NOT_UNCHANGED_FROM_FORK:'+arm['id'])
            else:unknown.append('ARM_UNFINISHED:'+arm['id'])
            checks.append(check)
        intervals.sort(key=lambda x:x['start_unix'])
        for left,right in zip(intervals,intervals[1:]):
            if right['start_unix']<left['end_unix']:errors.append('ARM_INTERVAL_OVERLAP:'+left['id']+':'+right['id'])
        owner['arm_intervals']=intervals
    owners.sort(key=lambda x:x['start_unix'])
    for left,right in zip(owners,owners[1:]):
        if right['start_unix']<left['audit_interval_end_unix']:errors.append('PATIENT_OWNER_INTERVAL_OVERLAP:'+str(left.get('patient_id'))+':'+str(right.get('patient_id')))
    if not records:unknown.append('NO_OBSERVED_ATTEMPTS')
    return dict(status='FAIL' if errors else 'IN_PROGRESS' if any(not r['closed'] for r in records) else 'UNKNOWN' if unknown else 'PASS',
        owners=owners,parent_hash_checks=checks,frozen_blocking_wait_sources=source,errors=errors,unknown_evidence=unknown,
        scope='Recorded study-owned process tree. Parent envelope overlap with its child is expected: the frozen harness blocks in waitpid, and saved before/after parent hashes must agree. This does not certify unrelated host processes.')
def preservation(full=True):
    before=read('audit/HISTORY_BEFORE.json');changed=[];missing=[];checked=0;total=0
    start=time.time()
    for path,entry in before.items():
        f=Path(path)
        if not f.exists():missing.append(path);continue
        h=sha(f) if full else (entry['sha256'] if f.stat().st_size==entry['size'] and f.stat().st_mtime_ns==entry['mtime_ns'] else sha(f))
        if h!=entry['sha256']:changed.append(path)
        checked+=1;total+=f.stat().st_size
    baseline=read('audit/GIT_BEFORE.json')
    main=Path('/home/hank/coding/adaptive-traction-mpc-learning');env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    git={n:subprocess.check_output(['git','-C',str(main),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]};git['index_sha256']=sha(main/'.git/index')
    put('audit/GIT_AFTER.json',git)
    result=dict(status='PASS' if not changed and not missing and git==baseline else 'FAIL',changed=changed,missing=missing,checked_files=checked,checked_bytes=total,full_rehash=full,git_exact_equal=git==baseline,wall_seconds=time.time()-start,unix=time.time())
    put('audit/HISTORY_PRESERVATION.json',result)
    manifest=read('EXECUTION_CODE_MANIFEST.json')['files'];errors=[rel for rel,h in manifest.items() if not (P/rel).exists() or sha(P/rel)!=h]
    put('audit/FROZEN_SOURCE_VERIFICATION.json',dict(status='PASS' if not errors else 'FAIL',errors=errors,files=len(manifest),unix=time.time()))
    print('PRESERVATION',result['status'],checked,'source_errors',len(errors),flush=True)
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=P)
    parser.add_argument('--preservation',action='store_true')
    args=parser.parse_args();P=args.package
    accounting()
    if args.preservation:preservation(full=True)
