from common import *
from interface import CoordinationInterface
from schedule import ResidualAction
def phase_data(z,phase,key):
 mask=(z['stage']=='TASK')&(z['task_phase']==phase);q=z[key][mask];t=z['time_s'][mask];s=(t-t[0])/(t[-1]-t[0]);return s,q
def main():
 table=json.loads((S/'docs/single_human_sac_expert_v1/r2/SAC_COMPARATOR_TABLE.json').read_text())['rows']
 rows={r['name']:r for r in table if r['scope']=='MATCHED'}
 base=np.load(O/'B_zero_interface/trace.npz');interface=CoordinationInterface();grid=np.linspace(0,1,1001);report=[];actions={}
 for name in ('old_nominal','fixed_hip_lead','cem_reference_transfer'):
  row=rows[name];z=np.load(R/row['trace']);entry=dict(name=name,trace=row['trace'],trace_hash=sha(R/row['trace']),J_F=row['J_F'],phase_durations=row['phase_durations'],category='historical R2 MATCHED characterization; no causal attribution',phases={})
  fitted={}
  for phase in ('OUTBOUND','RETURN'):
   tape=interface.tapes[phase];origin=tape.q[0];span=tape.span
   for key in ('reference_q_rad','evaluation_only_human_state_rad_rad_s'):
    bs,bq=phase_data(base,phase,key);hs,hq=phase_data(z,phase,key);bq=bq[:,:2];hq=hq[:,:2]
    bp=np.stack([np.interp(grid,bs,(bq[:,j]-origin[j])/span[j]) for j in range(2)],axis=1)
    hp=np.stack([np.interp(grid,hs,(hq[:,j]-origin[j])/span[j]) for j in range(2)],axis=1)
    delta=hp-bp;dm=delta.mean(axis=1);dd=(delta[:,0]-delta[:,1])/2
    character=dict(common_difference_rms=float(np.sqrt(np.mean(dm**2))),common_difference_peak=float(np.max(np.abs(dm))),coordination_difference_rms=float(np.sqrt(np.mean(dd**2))),coordination_difference_peak=float(np.max(np.abs(dd))),common_squared_fraction=float(np.sum(dm**2)/(np.sum(dm**2)+np.sum(dd**2)+1e-30)),endpoint_differential=[float(dd[0]),float(dd[-1])])
    entry['phases'].setdefault(phase,{})[key]=character
    if key=='reference_q_rad':
     # A pure joint PATH is d(m), not d at the historical wall clock. Re-time
     # the historical differential path to B's m without changing B pacing.
     bm=bp.mean(axis=1);bd=(bp[:,0]-bp[:,1])/2
     hm=hp.mean(axis=1);hd=(hp[:,0]-hp[:,1])/2
     character['historical_m_backtrack_total']=float(-np.sum(np.minimum(np.diff(hm),0.)))
     character['historical_m_largest_backstep']=float(-min(0.,np.min(np.diff(hm))))
     character['path_graph_fit_rule']='sort m and use first value for duplicate m; backtracking magnitude disclosed; approximate graph, no exact full-path claim'
     unique,ix=np.unique(hm,return_index=True)
     path_d=np.interp(bm,unique,hd[ix]);path_dd=path_d-bd
     locations=np.linspace(0.,1.,101);values=np.interp(locations,grid,path_dd);values[0]=values[-1]=0
     action=ResidualAction(phase,0.,(0.,0.,0.),tuple(zip(locations[1:].tolist(),values[1:].tolist())),1.,provenance='historical_pure_differential_'+name)
     realized=action.realize()(grid);character['residual_fit_rms']=float(np.sqrt(np.mean((realized-path_dd)**2)));character['residual_fit_peak']=float(np.max(np.abs(realized-path_dd)))
     character['path_fit_semantics']='historical d(m) retimed to B m(t); baseline relative differential only'
     character['normalized_joint_path_rms']=float(np.sqrt(np.mean((realized-path_dd)**2)))
     character['projected_vs_historical_joint_path_rms_rad']=float(np.sqrt(np.mean((span[None,:]*np.stack([-dm,-dm],axis=1))**2)))
     fitted[phase]=action.record()
  report.append(entry);actions[name]=fitted
 save('HISTORICAL_DECOMPOSITION.json',dict(rows=report,alignment='normalized phase clock, 1001 points, each B reference phase endpoint ROM; reference and physical decomposition separate',warning='MATCHED phase durations do not equal common progress. Modal energy fractions characterize path differences; they are not causal fractions of J_F benefits.',historical_segment_timing='Older 1.3x segment MATCHED evidence is a separate scope; new R2 transferred references analyzed here; historical CEM native optimum is not equated to these transfers.'))
 save('HISTORICAL_ACTIONS.json',actions)
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
