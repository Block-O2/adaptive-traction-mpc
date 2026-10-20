from common import *
for ident in ['parent_train_0_OUTBOUND_0_candidate0','parent_train_0_OUTBOUND_2_candidate0','parent_train_0_RETURN_1_candidate0']:
 p=MATRIX/'output'/(ident+'_DATA.json');r=load(p);at=r['child']['physical_time_at_fork'];z=np.load(MATRIX/'source/results'/ident/'trace.npz');t=z['time_s'];task=z['stage']=='TASK';v=z['interval_force_cost_n_s'];near=np.flatnonzero(abs(t-at)<.011)
 print(ident,'y',r['remaining_J_F'],'prefix',r['child']['start_J_F'],'native_vs_eval',r['metric']['tick_integral_vs_evaluation_J_F_error'],'at',at,'near',[(float(t[i]),str(z['stage'][i]),float(v[i])) for i in near],'sumtask',float(sum(v[task])),'sumfuture_ge',float(sum(v[task & (t>=at-1e-8)])),'sumfuture_gt',float(sum(v[task & (t>at+1e-8)])),flush=True)
