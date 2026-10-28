"""Evaluation-only extrema timing, no new state/physics or altered qualification."""
from pathlib import Path
import json,sys,time
import numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from acl2_shared import read,put,sha
g=sys.argv[1];rows=[]
for tag in ['B','V6PHASE','COMPOSE','BEST']:
 id=g+'_'+tag;r=read('attempts/'+id+'_RESULT.json');assert r['complete'];raw=P/'runtime/source/results'/id
 su=json.loads((raw/'summary.json').read_text());trans={x['to']:x['time_s'] for x in su['task']['phase_transitions']}
 f=P/'runtime/motion_series'/(id+'.npz')
 with np.load(f) as z:t=z['time_s'];q=np.degrees(z['true_q_rad']);assert t[0]<trans['HOLD']<trans['RETURN']<trans['COMPLETE']+1e-7
 def phase(ts):return 'OUTBOUND' if ts<trans['HOLD'] else 'HOLD' if ts<trans['RETURN'] else 'RETURN'
 extrema=[]
 for j,name in enumerate(['hip','knee']):
  lo=int(np.argmin(q[:,j]));hi=int(np.argmax(q[:,j]));extrema.append({'joint':name,'min_deg':float(q[lo,j]),'min_at_s':float(t[lo]),'min_phase':phase(t[lo]),'max_deg':float(q[hi,j]),'max_at_s':float(t[hi]),'max_phase':phase(t[hi]),'excursion_deg':float(q[hi,j]-q[lo,j])})
 phase_extrema={ph:{'min_deg':q[(t>=lo-1e-9)&(t<=hi+1e-9)].min(axis=0).tolist(),'max_deg':q[(t>=lo-1e-9)&(t<=hi+1e-9)].max(axis=0).tolist()} for ph,lo,hi in [('OUTBOUND',t[0],trans['HOLD']),('HOLD',trans['HOLD'],trans['RETURN']),('RETURN',trans['RETURN'],t[-1])]}
 rows.append({'id':id,'original_qualified':r['qualified'],'original_failed_requirements':r['motion_vs_B']['failed_requirements'],'original_excursion_delta_deg_vs_B':r['motion_vs_B']['excursion_delta_deg'],'extrema':extrema,'phase_extrema':phase_extrema,'motion_source_sha256':sha(f),'original_result_sha256':sha(P/'attempts'/(id+'_RESULT.json'))})
base=rows[0]
for row in rows:
 for j,e in enumerate(row['extrema']):
  e['upper_bound_shift_vs_B_deg']=e['max_deg']-base['extrema'][j]['max_deg'];e['lower_bound_shift_vs_B_deg']=e['min_deg']-base['extrema'][j]['min_deg'];e['range_shift_vs_B_deg']=e['excursion_deg']-base['extrema'][j]['excursion_deg']
out={'group':g,'status':'COMPLETED_EVALUATION_ONLY','created_unix':time.time(),'source_sha256':sha(Path(__file__)),'rows':rows,'original_threshold_unchanged':True,'causal_limit':'Extrema timing localizes which motionwindow differs; it does not identify a causal parameter repair, qualification predictor, or physicalsafety guarantee','new_physics':0,'new_training':0}
put('analysis/'+g+'_EXCURSION_MECHANISM.json',out);print('EXCURSION_EXTREMA',json.dumps(rows,ensure_ascii=False))
