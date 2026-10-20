"""Small, pre-training shared action audit; physical feasibility uses native v2."""
from study_common import *
import numpy as np

def fractions(K):
 return np.asarray(TIMINGS.get(K,np.linspace(0,1,K+2)[1:-1]))
TIMINGS={}
def basis(K,grid,start=0.):
 knots=np.r_[start,start+(1-start)*fractions(K),1.]
 out=[]
 for j in range(K):
  values=np.zeros(K+2);values[j+1]=1
  out.append(np.interp(grid,knots,values,left=0,right=0))
 return np.array(out).T

def fit(K,graph,start=0.):
 grid=np.linspace(start,1,1001)
 y=np.interp(grid,np.asarray(graph)[:,0],np.asarray(graph)[:,1])
 coef=np.linalg.lstsq(basis(K,grid,start),y,rcond=None)[0]
 error=basis(K,grid,start)@coef-y
 return coef,dict(normalized_rms=float(np.sqrt(np.mean(error**2))),normalized_peak=float(np.max(np.abs(error))),endpoint_zero=True,amplitude=float(np.max(np.abs(coef))))

def graph_action(values,start=0.):
 knots=np.r_[start,start+(1-start)*fractions(len(values)),1.]
 pairs=np.column_stack([knots,np.r_[0.,values,0.]]).tolist()
 return ([[0.,0.]] if start>0 else [])+pairs

def audit():
 assert read('REGRESSION_GATE.json')['pass_']
 sources=json.loads((W.parent/'coordination_residual_realization_v2/output/HISTORICAL_SPATIAL_GRAPH.json').read_text())
 graphs={}
 for name,record in sources.items():
  for phase,src in record['targets'].items():
   grid=np.linspace(0,1,1001)
   b=src['nominal_B_native_target_graph']
   residual=np.interp(grid,src['m'],src['d'])-np.interp(grid,b['m'],b['d']);residual[[0,-1]]=0
   graphs[name+'_'+phase]=np.column_stack([grid,residual]).tolist()
 for name in ('catchup','reversal'):
  graphs[name]=gates.pattern(name,.01)['OUTBOUND']
 rows=[]
 for K in (1,2,3):
  # Bounded common knot-timing audit, before any actor/training. Shared
  # timings are chosen across both fixed/CEM paths, never per-policy.
  candidates={1:[[.5]],2:[[a,b] for a in (.1,.15,.2,.25,.3) for b in (.7,.75,.8,.85,.9)],3:[[.15,.5,.85],[.2,.5,.8],[.25,.5,.75]]}[K]
  scores=[]
  for timing in candidates:
   TIMINGS[K]=timing
   score=max(fit(K,g)[1]['normalized_rms'] for name,g in graphs.items() if 'MATCHED' in name)
   scores.append((score,timing))
  score,timing=min(scores);TIMINGS[K]=timing
  fits={name:dict(coefficients=fit(K,g)[0].tolist(),**fit(K,g)[1]) for name,g in graphs.items()}
  reversal=fits['reversal']['coefficients'];sign_reversal=min(reversal)<-1e-4 and max(reversal)>1e-4
  rms=max(v['normalized_rms'] for name,v in fits.items() if 'MATCHED' in name)
  rows.append(dict(K=K,knot_fractions=timing,timing_candidates=len(candidates),fits=fits,history_max_rms=rms,can_reverse=sign_reversal,endpoint_compatible=True,qualifies=rms<=.01 and sign_reversal))
 choices=[r for r in rows if r['qualifies']]
 save('REPRESENTATION_AUDIT.json',dict(rows=rows,physical_feasibility='native v2 scheduler screens every proposal; selected K cold physical reference gates follow',category='pre-training representation development'))
 # Static full-phase fitting is stricter than the requested receding chunks.
 # If it misses the preference, require a cold physical path gate before BC.
 if not choices:choices=[r for r in rows if r['K']==2 and r['can_reverse'] and r['history_max_rms']<=.02]
 assert choices,'NO_REASONABLE_K_STOP'
 selected=choices[0];K=selected['K']
 bound=.2 # Room for point-constrained receding teacher fits; native safety unchanged.
 contract=dict(name='SHARED_COORDINATION_ACTION_CONTRACT',version=1,K=K,knot_fractions=selected['knot_fractions'],residual_units='dimensionless normalized task progress; p_hip=p_hip_B+delta, p_knee=p_knee_B-delta',residual_bounds=[-bound,bound],actor_units='K values in [-1,1] multiplied by residual bound',chunk_horizon='remaining spatial phase progress [current causal reference common progress, 1]; no wall-clock horizon',knot_timing='fixed interior fractions of remaining normalized-progress horizon; zero at current chunk origin and registered phase endpoint; native scheduler determines physical times',action_update='one action only at B native request decision with interior original selected nominal target; skip HOLD and terminal/settle requests; no timer-generated actions',phase_semantics='OUTBOUND start->goal; RETURN goal->start; positive delta leads hip in phase direction; independent chunks',execution='arbitrary PWL v2 residual_spec sampled at original B target; original scheduler/governor owns q/dq/ddq, wait, safety and feasibility',zero='all-zero graph => exact B',frozen_before_training=True,after_formal_start_immutable=True)
 save('SHARED_COORDINATION_ACTION_CONTRACT.json',contract)
 save('REPRESENTATION_SELECTION.json',dict(K=K,static_history_rms=selected['history_max_rms'],static_preference_met=selected['history_max_rms']<=.01,required_physical_receding_path_rms=.01,status='PROVISIONAL_PENDING_NATIVE_PHYSICAL_GATES'))
 text='# Shared E/V coordination action contract\n\n'+json.dumps(contract,indent=2)+'\n'
 for d in (L,D):(d/'SHARED_COORDINATION_ACTION_CONTRACT.md').write_text(text)
 save('REPRESENTATION_GRAPHS.json',graphs)
 state('REPRESENTATION_SELECTED',K=K,residual_bound=bound,history_max_rms=selected['history_max_rms'],training_interactions=0)
if __name__=='__main__':audit()
