from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
for name in ('hold_request_collection.py','fast_runtime.py'):shutil.copy2(S/'code'/name,S/'versions'/('C11a_'+name))
p=S/'code/hold_request_collection.py';t=p.read_text();t=t.replace('C11: one bounded','C12: one bounded',1)
old=" target=wall.epoch_ns+(wall._last_poll_grid+1)*wall.sensor_steps*wall.dt_ns\n deadline=min(target,request.sensor_capture_ns+life.maximum_age_ns)\n begin=wall.clock();before=wall.steps"
new=" regular_target=wall.epoch_ns+(wall._last_poll_grid+1)*wall.sensor_steps*wall.dt_ns\n begin=wall.clock();before=wall.steps\n period=wall.sensor_steps*wall.dt_ns\n current_target=wall.epoch_ns+((begin-wall.epoch_ns)//period+1)*period\n target=max(regular_target,current_target)\n deadline=min(target,request.sensor_capture_ns+life.maximum_age_ns)"
assert t.count(old)==1;t=t.replace(old,new)
t=t.replace("deadline_ns=deadline,socket_observed_ns=observed", "deadline_ns=deadline,previous_poll_deadline_ns=regular_target,current_absolute_grid_deadline_ns=current_target,socket_observed_ns=observed")
ast.parse(t);p.write_text(t)
p=S/'code/fast_runtime.py';t=p.read_text();assert "FAST_RUNTIME_SOURCE_VERSION']='C11a'" in t;t=t.replace("FAST_RUNTIME_SOURCE_VERSION']='C11a'","FAST_RUNTIME_SOURCE_VERSION']='C12'",1);p.write_text(t)
for name,base,diag in [('031_C12_science_nominal','027_C11a_science_nominal',False),('032_C12_science_deviation','028_C11a_science_deviation',False),('033_C12_host_nominal_diagnostic','029_C11a_host_nominal_diagnostic',True),('034_C12_host_deviation_diagnostic','030_C11a_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C12_CURRENT_GRID',dependencies=[],required_gates=['output/C12_LOCAL_EQUIVALENCE.json','output/C10_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['031_C12_science_nominal','032_C12_science_deviation'],required_gates=cfg['required_gates']+['versions/031_C12_science_nominal_SCI_GATE.json','versions/032_C12_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C12 registered; absolute original 5ms grid retained')
