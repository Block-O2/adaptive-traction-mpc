from pathlib import Path
import sys,ast,json,time
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
sys.path.insert(0,str(R/'control'));from early_features import vector
script=(R/'control/prepare_test.py').read_text();start=script.index("s=(P/'control/campaign_v2.py')");end=script.index("(P/'control/campaign_v3.py').write_text(s)");ns=dict(P=P);exec(script[start:end],ns);ast.parse(ns['s'])
rows=[]
for g in ['D01R','D02','D03','D04','D05','D06']:
    origin=json.loads((P/'audit'/(g+'_FORK_CONTEXT.json')).read_text())['physical_s'];cond=json.loads((P/(g+'_PLAN.json')).read_text())['condition'];xs=[]
    for a in ['B','H150','HIP','KNEE','ZERO']:
        z=np.load(P/'source/results'/(g+'_'+a)/'trace.npz');i=int(np.flatnonzero((z['stage']=='TASK')&(z['time_s']<origin-1e-9))[-1]);first=int(np.flatnonzero(z['stage']=='TASK')[0]);assert 0<origin-z['time_s'][i]<=.0100001
        xs.append(vector(z['estimated_human_state_rad_rad_s'][i],z['reference_q_rad'][i],z['reference_dq_rad_s'][i],z['physical_cuff_force_world_n'][i],z['physical_cuff_moment_world_nm'][i],z['time_s'][i]-z['time_s'][first],cond['prefix']['RETURN'][0]))
    assert all(np.array_equal(xs[0],x) for x in xs[1:]);rows.append(dict(parent=g,all_five_early_contexts_exact=True,features=xs[0].tolist()))
(P/'audit/EARLY_DESIGN_PRECHECK.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),generated_v3_AST=True,rows=rows,new_physics=0),indent=2)+'\n');print('EARLY_DESIGN_PRECHECK_PASS',flush=True)
