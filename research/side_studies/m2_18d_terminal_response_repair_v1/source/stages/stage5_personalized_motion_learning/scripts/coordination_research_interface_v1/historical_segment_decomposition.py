from common import *
from decompose import phase_data
from schedule import ResidualAction
def main():
 root=S/'results/best_known_coordination_search_v2/runs';db=json.loads((S/'docs/best_known_coordination_search_v2/BEST_KNOWN_REFERENCE_DATABASE.json').read_text())
 cem=next(x for x in db['entries'] if x['condition']=='sync_120' and x['matched_native_label']=='MATCHED')
 paths={'original_segment_MATCHED':root/'A_sync_120_MATCHED_baseline_0','fixed_hip_segment_MATCHED':root/'A_sync_120_MATCHED_fixed_0','CEM_segment_MATCHED':(R/cem['result_path']).parent}
 traces={name:np.load(next(folder.glob('rep_*/trace.npz'))) for name,folder in paths.items()};base=traces['original_segment_MATCHED'];grid=np.linspace(0,1,1001);rows=[]
 for name,z in traces.items():
  folder=paths[name];result=json.loads((folder/'rollout_result.json').read_text());item=dict(name=name,scope='historical_1.3x_segment_MATCHED_only',result_path=str(folder/'rollout_result.json'),result_hash=sha(folder/'rollout_result.json'),trace_hash=sha(next(folder.glob('rep_*/trace.npz'))),historical_metrics={k:v for k,v in result.items() if any(t in k for t in ('duration','J_F','clearance','force','moment','status'))},phases={})
  for phase in ('OUTBOUND','RETURN'):
   for key in ('reference_q_rad','evaluation_only_human_state_rad_rad_s'):
    bs,bq=phase_data(base,phase,key);hs,hq=phase_data(z,phase,key);bq=bq[:,:2];hq=hq[:,:2];origin=bq[0];span=bq[-1]-origin
    bp=np.array([np.interp(grid,bs,(bq[:,j]-origin[j])/span[j]) for j in range(2)]).T
    hp=np.array([np.interp(grid,hs,(hq[:,j]-origin[j])/span[j]) for j in range(2)]).T
    dm=(hp-bp).mean(axis=1);dd=((hp-bp)[:,0]-(hp-bp)[:,1])/2
    stats=dict(common_rms=float(np.sqrt(np.mean(dm**2))),coordination_rms=float(np.sqrt(np.mean(dd**2))),common_squared_fraction=float(np.sum(dm**2)/(np.sum(dm**2)+np.sum(dd**2)+1e-30)))
    item['phases'].setdefault(phase,{})[key]=stats
  rows.append(item)
 save('HISTORICAL_SEGMENT_DECOMPOSITION.json',dict(rows=rows,comparison='each historical candidate vs its own 1.3x segment baseline; never numerically ranked against R2 B',claim='modal trajectory characterization; no causal attribution of force-cost benefit'))
 print(json.dumps([dict(name=x['name'],phases=x['phases']) for x in rows]),flush=True)
if __name__=='__main__':main()
