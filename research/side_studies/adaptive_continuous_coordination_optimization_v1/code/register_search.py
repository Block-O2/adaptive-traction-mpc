from pathlib import Path
import json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1')
OLD=S.parent/'m2_matched_bidirectional_exploration_v1'
def put(n,x):(S/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def slot(amp,shape='flat',knots=None,support=None):
 values={'flat':[1,1,1],'ramp':[.2,.6,1],'taper':[1,.6,.2],'tent':[.2,1,.2],'reverse':[1,-.5,.25]}[shape]
 return dict(kind='PWL',amplitude=amp,shape=shape,knots=knots or [.1,.4,.7],values=[amp*v for v in values],support=support or [0,1],domain='remaining_causal_progress')
def policy(phase,amp,profile):
 masks={'all_flat':list(range(5)),'all_ramp':list(range(5)),'early_tent':[0,1],'late_taper':[2,3,4]}
 shape={'all_flat':'flat','all_ramp':'ramp','early_tent':'tent','late_taper':'taper'}[profile]
 return {phase:[slot(amp,shape) if i in masks[profile] else None for i in range(5)]}
def main():
 assert not (S/'SEARCH_PROTOCOL.json').exists()
 old=json.loads((OLD/'EXPERIMENT_PROTOCOL.json').read_text());rows=[]
 for ph in ['OUTBOUND','RETURN']:
  for amp in [-.12,-.04,-.01,.01,.04,.12]:
   for profile in ['all_flat','all_ramp','early_tent','late_taper']:
    rows.append(dict(id=f'C1_{len(rows):03d}',stage='C1',phases=policy(ph,amp,profile),parameters=dict(phase=ph,amplitude=amp,profile=profile)))
 for tag in ['O','R','OR']:
  rows.append(dict(id='REF_'+tag,stage='REFERENCE',table=old['candidates'][tag],parameters=dict(historical_reference=tag)))
 # Fixed joint coverage, followed by exactly defined combinations of measured single-stage leaders.
 for j in range(20):
  oa=[-.04,-.01,.01,.04,.08][j%5];ra=[-.08,-.03,.015,.06][j//5]
  op=['all_flat','all_ramp','early_tent','late_taper'][j%4];rp=['late_taper','all_flat','all_ramp','early_tent'][(j*3)%4]
  rows.append(dict(id=f'C2_fixed_{j:02d}',stage='C2',phases={**policy('OUTBOUND',oa,op),**policy('RETURN',ra,rp)},parameters=dict(O_amp=oa,R_amp=ra,O_profile=op,R_profile=rp)))
 for ph in ['OUTBOUND','RETURN']:
  for sign in [-1,1]:
   for j in range(6):
    shapes=['flat','ramp','taper','tent','reverse','tent'];knots=[[.03,.18,.45],[.2,.55,.9],[.05,.5,.95],[.2,.4,.6],[.1,.35,.8],[.08,.3,.6]]
    support=[[0,.6],[0,1],[.1,1],[.15,.8],[0,1],[0,.85]][j]
    specs=[slot(sign*.025,shapes[j],knots[j],support) if j==5 or i==j else None for i in range(5)]
    rows.append(dict(id=f'C3_{len(rows):03d}',stage='C3',phases={ph:specs},parameters=dict(phase=ph,amplitude=sign*.025,shape=shapes[j],slot='all' if j==5 else j,knots=knots[j],support=support)))
 plan=json.loads((S/'RUN_PLAN.json').read_text())
 protocol=dict(version='COMPREHENSIVE_COORDINATION_SEARCH_v1',registered_unix=time.time(),**plan,seed=2026101201,random_sampling_seed=2026101200,clock='SCIENTIFIC_MATCHED_EXECUTION',host_clock_qualification='NOT_EVALUABLE',search_bound_normalized_delta=[-.2,.2],native_bound='raw graph finite sorted [0,1] endpoints zero; no explicit amplitude clamp; modified normalized targets and native feasibility enforce legality',K3_knots=[.1,.4,.7],issued_slots_per_phase=5,dimensions=['phase','sign','amplitude','slot_mask','remaining_progress_onset','remaining_progress_support','PWL_knot_locations','PWL_shape','joint_phase_independent_parameters','within_phase_slot_combination'],budgets=dict(fork_and_baseline=8,C1=48,C2=32,C3=24,C4=24,validation=24,total_cap=160),primary_gain_percent=.5,motion_protocol_sha256=hashlib.sha256((S/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest(),C2_adaptive_rule='12 joint pairs: O top 3 by valid motion then J_F, R top 4 by same rule; combine independently, no holdout influence',C4_rule='after all broad stages: choose best motion-accepted candidate in each of 3 distinct stage/phase regions; if unavailable choose task-valid by least max burden then J_F; 8 factors [.6,.8,.9,1.1,1.2,1.4,-.5,-1] per region; amplitudes clipped to preregistered +/- .2, no hidden evaluations',selection_rule='eligible = task/native ownership PASS, nonzero residual in all targeted phases, motion acceptance PASS, J_F gain >=0.5%; freeze max3 representatives: minimum J_F, minimum max raw burden among eligible, most distinct parameter region among eligible; deduplicate; no reselect after validation',validation_conditions=[dict(name='H1',seed=2026101202,prefix={'OUTBOUND':[[.30,-.10,.05]]}),dict(name='H2',seed=2026101203,prefix={'OUTBOUND':[[-.15,.25,-.20]]})],validation_scope='two independent parent processes and legal prefix conditions not used for this search; existing Human and previously exposed prefix family, no population generalization; fork after common prefix at next lawful OUTBOUND request',validation_rule='B and Frozen M2 and frozen representatives on both conditions; each representative requires both gain>=0.5% and motion/native PASS; if no discovery eligible skip formal validation',early_stop=['same-control fork FAIL','parent mutated','native safety or ownership FAIL','dispatch cutoff','attempt cap','D free <20GiB','Linux available memory <1GiB','study storage >12GiB','three consecutive failed attempts'],storage='all compact metrics and parameter rows; compressed native traces retained under 12GiB cap for training-label value; no historical deletions',truth_firewall='fixed parameters and measured discovery outcomes only for bounded offline search; candidate context causal planner observation; simulator truth evaluation only',no_training=True,no_online_adaptation=True,no_B_core_semantic_changes=True)
 put('SEARCH_PROTOCOL.json',protocol);put('CANDIDATE_CATALOG.json',dict(frozen_unix=time.time(),candidates=rows,pending_C2_pairs=12,pending_C4=24))
 files=[S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py',S/'deps/coordination_adapter.py',S/'deps/representation.py',S/'deps/fork_core.py',S/'code/interfaces.py']
 action=dict(source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},fixed_K3='ordinary pool budget6: zero/carry/historical/coherent signs/reversal with seeded noise; sparse 30D coverage',continuous_K3='2 phases x 5 slots x3 amplitudes [-1,1]*.2 at .1/.4/.7 remaining progress',raw_v2='arbitrary finite PWL, sorted knots, zero (0,0)/(1,0), native sample at original target common progress; p modified by [delta,-delta]; endpoints and HOLD B owned',physical_execution='same existing proposal boundary, native scheduler/governor feasibility, current-state admission, lifecycle, original applied receipts/native steps; no new clocks or torque authority',dimensions={d:dict(range=protocol['search_bound_normalized_delta'] if d=='amplitude' else '[0,1] normalized remaining progress' if 'progress' in d or 'knot' in d else 'finite registered catalog',units='dimensionless progress or issued slot index',native_legal='parameter validity plus original feasibility/admission; proposed alone insufficient',actual_location='sampled once at each original native interior target request',execution_verified=False) for d in protocol['dimensions']},unsupported=['common-progress shift','independent hip/knee offsets','dq/ddq command','phase duration control','HOLD/terminal residual','continuous temporal PWL actuation'],limitation='different raw shapes with equal sampled delta at a request may be physically equivalent; finite search neither exhaustive nor mathematical optimum')
 put('ACTION_SPACE_MAP.json',action)
 (S/'ACTION_SPACE_MAP.md').write_text('# 可执行动作空间审计\n\n'+json.dumps(action,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(dict(registered=len(rows),C1=48,C2_fixed=20,C3=24,reference=3,planned_adaptive=36)),flush=True)
if __name__=='__main__':main()
