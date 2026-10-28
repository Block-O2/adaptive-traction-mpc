"""No physics: reject timing-only and runtime-only formal promotion."""
from qualification_status import classify
from common import ROOT,put
base={'status':'COMPLETE','abort_reason':None,'task':{'physics_duration_s':19.03,'phase_transitions':[{'from':'OUTBOUND','to':'HOLD'},{'from':'HOLD','to':'RETURN'},{'from':'RETURN','to':'COMPLETE','trigger':'causal_return_actual_completion_commit'}]}}
m={'success':True,'phases':['OUTBOUND','HOLD','RETURN'],'task_s':19.03}
checks=[]
x=classify(m,base,{'pass':True});checks.append({'test':'19_030_runtime_success_cannot_promote_full_or_matched','pass':x['RUNTIME_COMPLETE']=='PASS' and x['MATCHED_19_030_NECESSARY_TIMING']=='PASS' and x['MATCHED_TASK_PASS'].startswith('NOT_READY') and x['FULL_QUALIFIED'].startswith('NOT_READY')})
y=classify({**m,'task_s':20.165},{**base,'task':{**base['task'],'physics_duration_s':20.165}},{'pass':True});checks.append({'test':'runtime_longer_than_necessary_matched_timing_stays_distinct','pass':y['RUNTIME_COMPLETE']=='PASS' and y['MATCHED_19_030_NECESSARY_TIMING']=='FAIL'})
z=classify({**m,'phases':['OUTBOUND','RETURN']},base,{'pass':True});checks.append({'test':'missing_hold_cannot_runtime_complete','pass':z['RUNTIME_COMPLETE']=='FAIL'})
z=classify(m,{**base,'status':'ABORTED','abort_reason':'TASK_ACCELERATION_LIMIT'},{'pass':False});checks.append({'test':'safety_abort_overrides_success_flag','pass':z['RUNTIME_COMPLETE']=='FAIL' and z['OBSERVED_EPISODE_PHYSICS_AND_CAUSAL']=='FAIL'})
put(ROOT/'EVALUATOR_SEMANTICS_TESTS.json',{'category':'NO_PHYSICS_NEGATIVE_QUALIFICATION_TESTS','checks':checks,'pass':all(x['pass'] for x in checks)})
assert all(x['pass'] for x in checks)
print('PASS',len(checks))
