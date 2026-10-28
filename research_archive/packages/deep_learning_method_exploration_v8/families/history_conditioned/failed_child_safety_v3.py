"""Read-only closed failed-child attribution; no runtime import or physics.

Explicit original hard false stops. Missing hard evidence stops as UNKNOWN.
Motion qualification, completion/dwell and burden failures are not reclassified
as hard physical false. Incomplete JF is retained but never ranked.
"""
from pathlib import Path
import hashlib,json

HARD_FIELDS=('force','moment','torque','human_speed','human_acceleration','robot_speed',
    'session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation')


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _views(value,path=''):
    if not isinstance(value,dict):return
    for key,child in value.items():
        location=path+'/'+key
        if key=='scorer_v2_common_conditions' and isinstance(child,dict):yield location,child
        if key=='raw_scorer_v2' and isinstance(child,dict) and isinstance(child.get('conditions'),dict):yield location+'/conditions',child['conditions']
        if isinstance(child,dict):yield from _views(child,location)


def inspect_closed_failed_child(root,ident,*,failure,joined):
    root=Path(root)
    ledger=root/'runtime/ATTEMPTS.jsonl'
    events=[json.loads(s) for s in ledger.read_text().splitlines() if s.strip()] if ledger.is_file() else []
    start=[r for r in events if r.get('id')==ident and r.get('event')=='START']
    end=[r for r in events if r.get('id')==ident and r.get('event')=='END']
    if joined is not True or len(start)!=1 or len(end)!=1 or end[0].get('joined') is not True:
        return dict(id=ident,status='UNKNOWN_STOP_STAGE',reason='CLOSED_FAILED_CHILD_JOIN_NOT_VERIFIED',
            original_failure=failure,raw_documents_read=False,actual_new_native_steps=None,partial_never_ranked=True)
    candidates=[('RESULT',root/'attempts'/(ident+'_RESULT.json')),
        ('DATA',root/'runtime/output'/(ident+'_DATA.json')),
        ('PARTIAL',root/'runtime/output'/(ident+'_PARTIAL_COMPUTE.json')),
        ('PERSISTENT_DELTA',root/'audit/persistent'/(ident+'_PERSISTENT_DELTA_ACCOUNTING.json'))]
    sources=[];values={key:[] for key in HARD_FIELDS};costs=[];validity_false=[];read_errors=[]
    for kind,path in candidates:
        if not path.is_file():continue
        sources.append(dict(kind=kind,path=str(path),sha256=sha(path)))
        try:document=read(path)
        except (ValueError,OSError) as exc:
            read_errors.append(dict(source=kind,error=type(exc).__name__+':'+str(exc)));continue
        metric=document.get('metric',document)
        for location,checks in _views(document):
            for key in HARD_FIELDS:
                if key in checks:values[key].append(dict(source=kind,path=location+'/'+key,value=checks[key]))
        # These are original finite physical-state checks, not motion burden.
        def finite_walk(value,path=''):
            if not isinstance(value,dict):return
            for key,child in value.items():
                if key in ('finite_trace','finite_native') and child is False:validity_false.append(dict(source=kind,path=path+'/'+key))
                if isinstance(child,dict):finite_walk(child,path+'/'+key)
        finite_walk(document)
        count=document.get('actual_new_native_steps') if kind=='PERSISTENT_DELTA' else metric.get('actual_new_native_physics_steps',document.get('actual_new_native_steps'))
        costs.append(dict(source=kind,actual_new_native_steps=count,J_F_unranked=metric.get('J_F',document.get('JF')),
            JM_unranked=metric.get('moment_integral',document.get('JM')),task_valid=metric.get('task_valid'),
            absolute_native_index_not_new=metric.get('native_physics_steps')))
    bad=[key for key,rows in values.items() if any(r['value'] is False for r in rows)]
    unknown=[key for key,rows in values.items() if not rows or not any(r['value'] is True for r in rows)]
    status='HARD_FALSE_STOP_STAGE' if bad or validity_false else 'UNKNOWN_STOP_STAGE' if unknown or read_errors else 'HARD_FIELDS_CONFIRMED_TRUE_ONLY'
    preferred=next((r for kind in ('PERSISTENT_DELTA','DATA','PARTIAL','RESULT') for r in costs if r['source']==kind and isinstance(r['actual_new_native_steps'],int) and not isinstance(r['actual_new_native_steps'],bool) and r['actual_new_native_steps']>=0),None)
    distinct=sorted({r['actual_new_native_steps'] for r in costs if isinstance(r['actual_new_native_steps'],int) and not isinstance(r['actual_new_native_steps'],bool)})
    return dict(id=ident,status=status,original_failure=failure,closed_child_END=end[0],raw_documents_read=True,
        explicit_hard_false=bad,explicit_physical_finiteness_false=validity_false,unknown_hard_fields=unknown,
        original_hard_field_evidence=values,source_documents=sources,source_read_errors=read_errors,cost_candidates=costs,
        actual_new_native_steps=None if preferred is None else preferred['actual_new_native_steps'],
        count_source=None if preferred is None else preferred['source'],cost_counter_disagreement=len(distinct)>1,
        partial_never_ranked=True,motion_failure_alone_does_not_stop=True,
        scope='Confirmed hard fields only; never label the incomplete task or missing physical audit safe')
