"""Post-freeze ranking diagnostics. No fitting, candidate generation or new physics."""
from pathlib import Path
import os,sys,json,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
out=[]
for f in sorted((P/'analysis').glob('CRITIC_*_RESULTS.json')):
 d=json.loads(f.read_text())
 for r in d['results']:
  rows=r['rows'];actual=np.array([x['actual_tail_JF'] for x in rows]);pred=np.array([x['predicted_tail_components']['tail_JF'] for x in rows]);total=np.array([x['actual_full_remaining_JF'] for x in rows]);estimated=np.array([x['critic_total_JF'] for x in rows]);err=pred-actual;pair=[]
  for i in range(len(rows)):
   for j in range(i):
    delta=total[i]-total[j];guess=estimated[i]-estimated[j]
    if abs(delta)>1e-6:pair.append(dict(a=rows[i]['id'],b=rows[j]['id'],actual_delta=delta,predicted_delta=guess,order_correct=bool(delta*guess>0)))
  valid=sorted([x for x in rows if x['qualified']],key=lambda x:x['actual_full_remaining_JF']);by={x['id']:x for x in rows};sh=by[r['unrestricted_short_choice']];cr=by[r['unrestricted_critic_choice']];fx=by[r['fixed_training_choice']];long=by.get(r.get('one_second_short_choice'))
  out.append(dict(model=d['id'],test_group=r['group'],tail_JF_raw_RMSE=float(np.sqrt(np.mean(err**2))),tail_JF_common_error_N_s=float(np.mean(err)),tail_JF_within_menu_centered_RMSE=float(np.sqrt(np.mean((err-np.mean(err))**2))),pairwise_total_gap_RMSE=float(np.sqrt(np.mean([(x['predicted_delta']-x['actual_delta'])**2 for x in pair]))),pairwise_order_accuracy=float(np.mean([x['order_correct'] for x in pair])),pairwise_rows=pair,actual_best_to_second_gap_N_s=None if len(valid)<2 else valid[1]['actual_full_remaining_JF']-valid[0]['actual_full_remaining_JF'],critic_is_training_fixed_action=cr['id']==fx['id'],critic_vs_1s_short_JF_gain_N_s=None if long is None or not(long['qualified'] and cr['qualified']) else long['actual_full_remaining_JF']-cr['actual_full_remaining_JF'],actual_chosen_full_tasks={name:{k:z[k] for k in ['id','qualified','actual_full_task_JF','actual_full_task_JM','actual_motion_worst_ratio']} for name,z in [('short',sh),('critic',cr),('training_fixed',fx)]},uncertainty_scope='Reported ensemble disagreement is a model sensitivity descriptor only, not a calibrated safety/probability interval. All candidate full continuations were measured; no true attempt savings claimed.'))
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='POST_FROZEN_EVALUATION_ONLY',rows=out,interpretation='Tail cost contains state-common cost which can dominate absolute error. Centered and pairwise diagnostics evaluate the differences which affect a choice. No test feedback refits the frozen models.',new_physical_attempts=0)
(P/'analysis/CRITIC_RANKING_DIAGNOSTICS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print('RANK_DIAGNOSTICS',len(out))
