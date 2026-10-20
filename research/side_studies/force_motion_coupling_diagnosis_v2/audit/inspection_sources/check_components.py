from pathlib import Path
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1')
t=np.load(P/'source/results/development_B0/trace.npz');m=t['stage']=='TASK'
x=sum(t['robot_torque_component_'+k+'_nm'][m] for k in ['base','position','velocity','allocator','clipping'])
d=x-t['cr12_actuator_command_nm'][m];valid=np.isfinite(d).all(axis=1)
print('finite',sum(valid),'invalid',np.flatnonzero(~valid).tolist(),'finite_max',np.max(abs(d[valid])))
i=np.unravel_index(np.nanargmax(abs(d)),d.shape)[0]
print('max_at',t['time_s'][m][i],{k:t[k][m][i].tolist() for k in ['cr12_actuator_command_nm']+['robot_torque_component_'+k+'_nm' for k in ['base','position','velocity','allocator','clipping']]})
print('dec_keys',list(__import__('json').loads((P/'source/results/development_B0/summary.json').read_text())['decisions'][0]))
