from pathlib import Path
import json, numpy as np, gzip
P=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_autonomous_review_v1';Q=S/'m2_18d_baseline_qualification_v1'
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))+'\n')
out={}
for root,g,arm in [(A,'N2',a) for a in ['B','E','C','R']]+[(Q,'N1',a) for a in ['B','E']]:
 f=root/'source/results'/f'{g}_{arm}';su=json.loads((f/'summary.json').read_text());tr=np.load(f/'trace.npz');task=tr['time_s'][tr['stage']=='TASK'][0]
 rows=[]
 for lr in su['learning_records']:
  d=su['decisions'][lr['decision_index']];sp=lr.get('selected_plan',{});ss=sp.get('schedule',{})
  if d['decision_request_time_s']-task<9.01:
   rows.append(dict(index=lr['decision_index'],t=d['decision_request_time_s']-task,activation=None if d.get('actual_schedule_start_physics_s') is None else d['actual_schedule_start_physics_s']-task,schedule=ss,free=sp.get('execution_screen',{}).get('free_trajectory'),selected=sp.get('label'),decision=d,lr=lr))
 key=g+'_'+arm
 out[key]=dict(task_start=task,trace={k:[str(tr[k].dtype),list(tr[k].shape)] for k in tr.files},summary_keys=list(su),rows=rows,files=[str(p.relative_to(f)) for p in f.rglob('*') if p.is_file()])
 if key=='N2_E':
  z=np.load(f/'native_reference.npz');out[key]['reference_schema']={k:[str(z[k].dtype),list(z[k].shape),z[k][:2].tolist()] for k in z.files}
  z=json.loads(gzip.open(f/'runtime_artifacts.json.gz','rt').read());out[key]['runtime_keys']=list(z);out[key]['runtime_examples']={k:str(v)[:1600] for k,v in z.items()}
 print(key,'task_start',task,'schedules',[(r['index'],round(r['t'],4),round(r['activation'],4) if r['activation'] else None,r['schedule'].get('duration_s'),r['free'].get('status') if r['free'] else None) for r in rows],flush=True)
put('derived/PEEK.json',out)
