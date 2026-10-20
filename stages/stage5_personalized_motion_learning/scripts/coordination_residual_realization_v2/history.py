from gates import *
def graph(q,start,span):
 p=(q-start)/span;m=p.mean(axis=1);d=(p[:,0]-p[:,1])/2
 u,ix=np.unique(m,return_index=True)
 return u,d[ix],float(-np.minimum(np.diff(m),0).sum())
def prepare():
 base=json.loads((S/'results/coordination_research_interface_v1/B_original/summary.json').read_text())
 spec=registered_task_endpoints()
 start=np.asarray(spec['start_return_target_rad']);goal=np.asarray(spec['outbound_goal_target_rad']);grid=np.linspace(0,1,201)
 paths={'fixed_hip_segment_MATCHED':S/'results/best_known_coordination_search_v2/runs/A_sync_120_MATCHED_fixed_0/rep_01/trace.npz','CEM_segment_MATCHED':S/'results/best_known_coordination_search_v2/runs/B_sync_120_MATCHED_L1_R1_G0_C2/rep_01/trace.npz'}
 allactions={};sources={}
 for name,path in paths.items():
  z=np.load(path);action={};targets={}
  for phase in ('OUTBOUND','RETURN'):
   origin,span=(start,goal-start) if phase=='OUTBOUND' else (goal,start-goal)
   # Spatial graph only: no historical timestamps or dq interpreted as derivatives.
   mask=(z['stage']=='TASK')&(z['task_phase']==phase)
   hm,hd,back=graph(z['reference_q_rad'][mask],origin,span)
   ds=[d for d in base['decisions'] if d['phase']==phase]
   q=np.array([np.asarray(d['deployable_state_rad_rad_s'][:2])+np.asarray(d['executed_action_delta_q_rad']) for d in ds])
   bm,bd,_=graph(np.vstack([origin,q,origin+span]),origin,span)
   value=np.interp(grid,hm,hd)-np.interp(grid,bm,bd);ends=value[[0,-1]].tolist();value[[0,-1]]=0
   action[phase]=np.column_stack([grid,value]).tolist();targets[phase]=dict(m=hm.tolist(),d=hd.tolist(),backtracking=back,endpoint_zero_projection=ends,nominal_B_native_target_graph=dict(m=bm.tolist(),d=bd.tolist()))
  allactions[name]=action;sources[name]=dict(path=str(path),sha256=sha(path),targets=targets)
 save('HISTORICAL_ACTIONS_V2.json',allactions);save('HISTORICAL_SPATIAL_GRAPH.json',sources)
def execute():
 assert read('MINIMAL_GATE.json')['pass_']
 if not (L/'HISTORICAL_ACTIONS_V2.json').exists():prepare()
 sources=read('HISTORICAL_SPATIAL_GRAPH.json');native={}
 for kind,record in sources.items():
  native[kind]={}
  for phase,t in record['targets'].items():
   grid=np.linspace(0,1,201);d=np.interp(grid,t['m'],t['d']);ends=d[[0,-1]].tolist();d[[0,-1]]=0
   native[kind][phase]=dict(kind='historical_d_to_residual',knots=np.column_stack([grid,d]).tolist(),endpoint_zero_projection=ends)
 save('HISTORICAL_NATIVE_GRAPH_ACTIONS.json',native)
 rows=[]
 actions=native
 for kind in ('fixed_hip_segment_MATCHED','CEM_segment_MATCHED'):
  action=actions[kind]
  name='native_graph_'+kind
  m=read(name+'.json') if (L/(name+'.json')).exists() else run(name,Interface(action))
  row=audit(name,m);ref=np.load(O/name/'native_reference.npz');src=read('HISTORICAL_SPATIAL_GRAPH.json')[kind]
  base=registered_task_endpoints();start=np.array(base['start_return_target_rad']);goal=np.array(base['outbound_goal_target_rad']);errors={}
  for phase in ('OUTBOUND','RETURN'):
   origin,span=(start,goal-start) if phase=='OUTBOUND' else (goal,start-goal)
   q=ref['data'][ref['phase']==phase,1:3];em,ed,back=graph(q,origin,span);target=src['targets'][phase];grid=np.linspace(0,1,1001)
   err=np.interp(grid,em,ed)-np.interp(grid,target['m'],target['d']);errors[phase]=dict(normalized_path_rms=float(np.sqrt(np.mean(err**2))),normalized_path_peak=float(np.max(np.abs(err))),executed_backtrack=back)
  row.update(name=kind,path_errors=errors);row['pass_']=row['pass_'] and all(x['normalized_path_rms']<=.02 for x in errors.values());rows.append(row);save('HISTORICAL_GATE.json',dict(rows=rows,pass_=len(rows)==2 and all(r['pass_'] for r in rows)))
  print(json.dumps(dict(history=kind,pass_=row['pass_'],accepted=row['accepted'],path_errors=errors,J_F=m['J_F'])),flush=True)
if __name__=='__main__':
 import sys
 if len(sys.argv)>1 and sys.argv[1]=='prepare':prepare()
 else:execute()

