"""Synthetic offline tests. No controller, model, or physics execution."""
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('offline_account',ROOT/'account_and_verify.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def put(root,name,value):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')

def setup(root):
    sources={'serial_campaign.py':'child.wait(timeout=1)\n',
             'code/matched_harness.py':'os.waitpid(pid,0)\n','cross_runner.py':'# synthetic source only\n'}
    for rel,content in sources.items():
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    put(root,'EXECUTION_CODE_MANIFEST.json',{'files':{rel:hashlib.sha256((root/rel).read_bytes()).hexdigest() for rel in sources}})
    manifest=module.sha(root/'EXECUTION_CODE_MANIFEST.json')
    put(root,'RUN_PLAN.json',{'physics_budget':80,'dispatch_cutoff_unix':1000,'no_new_physics_after_unix':1000,'physical_timeout_s':10})
    put(root,'VIRTUAL_PATIENT_COHORT.json',{'patients':[{'patient_id':'P00'}]})
    put(root,'STATIC_PATIENT_AUDIT.json',{'records':[{'patient_id':'P00','model_static_valid':True}]})
    put(root,'audit/P00_OWNER.json',{'patient_id':'P00','start_unix':0,'end_unix':100,'joined':True})
    put(root,'audit/P00_FORK_CONTEXT.json',{'physical_s':5*module.DT,'task_s':module.DT})
    put(root,'reports/P00_PARENT_CHECKS.json',[{'id':'P00_'+arm,'unchanged':True,'before':'hash','after':'hash'} for arm in ['B','H150']])
    events=[]
    for arm,start,end in [('parent',10,90),('B',20,40),('H150',50,70)]:
        ident='P00_'+arm
        events.extend([{'event':'START','id':ident,'patient_id':'P00','unix':start,'source_sha256':manifest,'snapshot_hash':'hash'},
                       {'event':'END','id':ident,'unix':end,'joined':True}])
        inherited=0 if arm=='parent' else 5
        data={'metric':{'native_physics_steps':8,'actual_new_native_physics_steps':8-inherited,'simulation_seconds':8*module.DT},
              'child':None if arm=='parent' else {'physics_step_at_fork':inherited}}
        put(root,f'output/{ident}_DATA.json',data)
        put(root,f'reports/{ident}_SNAPSHOT.json',{'hash':'hash','manifest':{'task_last_physics_time':inherited*module.DT}})
        raw={'native_states_evaluation_only':[{'time_s':(i+1)*module.DT} for i in range(8)],
             'command_receipts':[{'applied':True,'native_steps':8,'start_physics_s':0,'end_physics_s':8*module.DT}]}
        path=root/f'source/results/{ident}/runtime_artifacts.json.gz';path.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(path,'wt') as stream:json.dump(raw,stream)
    ledger(root,events)
    return events

def ledger(root,events):
    (root/'ATTEMPTS.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events))

def run_case(name,change,assertion):
    with tempfile.TemporaryDirectory(prefix='ihear_accounting_synthetic_') as folder:
        root=Path(folder);events=setup(root);change(root,events)
        result=module.accounting(root,write=False);assertion(result)
        json.dumps(result,allow_nan=False)
    passed.append(name)

def expect(value):
    assert value

def modify_data(root,ident,fn):
    path=root/f'output/{ident}_DATA.json';data=json.loads(path.read_text());fn(data);put(root,str(path.relative_to(root)),data)

def incomplete(root,events):
    (root/'source/results/P00_H150/runtime_artifacts.json.gz').unlink()
    (root/'output/P00_H150_DATA.json').unlink()
    ledger(root,[e for e in events if not (e['id'] in ['P00_H150','P00_parent'] and e['event']=='END')])
    (root/'audit/P00_OWNER.json').unlink()
    put(root,'OWNED_ACTIVE_PROCESS.json',{'patient_id':'P00','start_unix':0})

def owner_overlap(root,events):
    parent=next(e for e in events if e['id']=='P00_parent' and e['event']=='START')
    events.extend([dict(parent,id='P01_parent',patient_id='P01',unix=95),{'event':'END','id':'P01_parent','unix':115,'joined':True}])
    ledger(root,events)
    put(root,'audit/P01_OWNER.json',{'patient_id':'P01','start_unix':90,'end_unix':130,'joined':True})
    shutil.copytree(root/'source/results/P00_parent',root/'source/results/P01_parent')
    shutil.copy2(root/'output/P00_parent_DATA.json',root/'output/P01_parent_DATA.json')

def receipt_mismatch(root,events):
    raw={'native_states_evaluation_only':[{'time_s':(i+1)*module.DT} for i in range(8)],
         'command_receipts':[{'applied':True,'native_steps':7,'start_physics_s':0,'end_physics_s':7*module.DT}]}
    with gzip.open(root/'source/results/P00_B/runtime_artifacts.json.gz','wt') as stream:json.dump(raw,stream)

def stage_boundaries(root,events):
    import numpy as np
    np.savez(root/'source/results/P00_parent/trace.npz',time_s=np.arange(9)*module.DT,
             stage=np.array(['COMMISSIONING']*2+['ACTIVE_RECOVERY']*2+['TASK']*5))

passed=[]
run_case('complete_counts_prefix_once',lambda r,e:None,lambda x:expect(x['status']=='PASS' and x['actual_new_native_steps']==14 and x['all_physics_serial'] is True and x['records'][0]['pre_task_native_steps']==4 and x['records'][0]['commissioning_native_steps'] is None))
run_case('missing_raw_is_unknown_not_zero',lambda r,e:(r/'source/results/P00_B/runtime_artifacts.json.gz').unlink(),lambda x:expect(x['status']=='UNKNOWN' and x['actual_new_native_steps'] is None and x['records'][1]['native_count_match'] is None))
run_case('snapshot_recovers_missing_child_data',lambda r,e:(r/'output/P00_B_DATA.json').unlink(),lambda x:expect(x['status']=='PASS' and x['records'][1]['inherited_prefix_native_steps']==5 and x['actual_new_native_steps']==14))
run_case('unknown_inheritance_never_defaults_zero',lambda r,e:((r/'output/P00_B_DATA.json').unlink(),(r/'reports/P00_B_SNAPSHOT.json').unlink()),lambda x:expect(x['status']=='UNKNOWN' and x['records'][1]['actual_new_native_steps'] is None))
run_case('duplicate_start_preserved_and_rejected',lambda r,e:ledger(r,e+[copy.deepcopy(e[0])]),lambda x:expect(x['status']=='FAIL' and x['START_count']==4 and x['unique_START_ids']==3 and x['actual_new_native_steps'] is None))
run_case('orphan_end_preserved_and_rejected',lambda r,e:ledger(r,e+[{'event':'END','id':'orphan','unix':80,'joined':True}]),lambda x:expect(x['status']=='FAIL' and x['orphan_END_ids']==['orphan']))
run_case('duplicate_end_rejected',lambda r,e:ledger(r,e+[copy.deepcopy(e[1])]),lambda x:expect(x['status']=='FAIL' and x['duplicate_END_ids']=={'P00_parent':2}))
run_case('negative_actual_delta_rejected',lambda r,e:(modify_data(r,'P00_B',lambda d:d.update(child={'physics_step_at_fork':9},metric={})),put(r,'reports/P00_B_SNAPSHOT.json',{'hash':'hash','manifest':{'task_last_physics_time':9*module.DT}})),lambda x:expect(x['status']=='FAIL' and 'NEGATIVE_ACTUAL_NEW_NATIVE_STEPS' in x['records'][1]['errors']))
run_case('declared_counter_disagreement_rejected',lambda r,e:modify_data(r,'P00_B',lambda d:d['metric'].update(actual_new_native_physics_steps=2)),lambda x:expect(x['status']=='FAIL' and 'INHERITED_COUNTER_SOURCES_DISAGREE' in x['records'][1]['errors']))
run_case('budget_exceeded',lambda r,e:put(r,'RUN_PLAN.json',{'physics_budget':2,'dispatch_cutoff_unix':1000,'physical_timeout_s':10}),lambda x:expect(x['status']=='FAIL' and x['budget_status']=='FAIL'))
run_case('dispatch_margin_violation',lambda r,e:put(r,'RUN_PLAN.json',{'physics_budget':80,'dispatch_cutoff_unix':60,'physical_timeout_s':15}),lambda x:expect(x['status']=='FAIL' and any(v['code']=='START_VIOLATES_FROZEN_TIMEOUT_MARGIN' for v in x['errors'])))
run_case('changed_parent_hash_rejected',lambda r,e:put(r,'reports/P00_PARENT_CHECKS.json',[{'id':'P00_B','unchanged':True,'before':'hash','after':'changed'}]),lambda x:expect(x['status']=='FAIL' and x['all_physics_serial'] is False))
run_case('arm_overlap_rejected',lambda r,e:ledger(r,[dict(v,unix=30) if v['id']=='P00_H150' and v['event']=='START' else v for v in e]),lambda x:expect(x['status']=='FAIL' and any(v.startswith('ARM_INTERVAL_OVERLAP') for v in x['serial_evidence']['errors'])))
run_case('active_attempt_retained_in_progress',incomplete,lambda x:expect(x['status']=='IN_PROGRESS' and x['actual_new_native_steps'] is None and x['unclosed_START_ids']==['P00_H150','P00_parent']))
run_case('missing_array_not_zero',lambda r,e:(r/'source/results/P00_B/runtime_artifacts.json.gz').write_bytes(gzip.compress(b'{"command_receipts": []}')),lambda x:expect(x['status']=='FAIL' and 'MISSING_ARRAY' in x['records'][1]['artifact_error']))
run_case('frozen_wait_source_changed',lambda r,e:(r/'code/matched_harness.py').write_text('os.waitpid(pid,1)\n'),lambda x:expect(x['status']=='FAIL' and x['all_physics_serial'] is False))
run_case('missing_ledger_not_zero',lambda r,e:(r/'ATTEMPTS.jsonl').unlink(),lambda x:expect(x['status']=='FAIL' and x['actual_new_native_steps'] is None))
run_case('patient_owner_overlap_rejected',owner_overlap,lambda x:expect(x['status']=='FAIL' and any(v.startswith('PATIENT_OWNER_INTERVAL_OVERLAP') for v in x['serial_evidence']['errors'])))
run_case('native_receipt_mismatch_rejected',receipt_mismatch,lambda x:expect(x['status']=='FAIL' and 'NATIVE_RECEIPT_COUNT_MISMATCH' in x['records'][1]['errors']))
run_case('commissioning_recovery_separated',stage_boundaries,lambda x:expect(x['status']=='PASS' and x['records'][0]['commissioning_native_steps']==2 and x['records'][0]['pre_task_native_steps']==4))
run_case('rawless_partial_counter_is_unverified',lambda r,e:((r/'source/results/P00_B/runtime_artifacts.json.gz').unlink(),put(r,'output/P00_B_PARTIAL_COMPUTE.json',{'actual_new_native_physics_steps':3,'simulation_seconds':8*module.DT})),lambda x:expect(x['status']=='UNKNOWN' and x['records'][1]['partial_declared_actual_new_steps']==3 and x['records'][1]['actual_new_native_steps'] is None))
run_case('configured_cap_cannot_exceed_80',lambda r,e:put(r,'RUN_PLAN.json',{'physics_budget':81,'dispatch_cutoff_unix':1000,'physical_timeout_s':10}),lambda x:expect(x['status']=='FAIL' and x['max_START']==80))
report={'status':'PASS','scope':'SYNTHETIC_ONLY_NOT_RESEARCH_RESULTS','tests':passed,'physics_starts':0,'training':False}
put(ROOT,'audit_protocol/ACCOUNTING_SYNTHETIC_VALIDATION.json',report)
print(json.dumps(report))
