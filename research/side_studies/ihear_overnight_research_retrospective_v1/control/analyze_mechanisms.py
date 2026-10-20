"""Matched probes and realized-plan evidence; no additional simulation."""
from pathlib import Path
import os,json,time
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
def load(p):return json.loads(p.read_text())
r=load(S/'EXPLORATION_RESULTS.json');selection=r['frozen_selection'];assert selection
best=selection['best'];selected=next(x for x in r['complete_evaluations'] if x['id']==best['id'])
prior=next(x for x in r['complete_evaluations'] if x['id']=='development_repair2_prior_best_18D')
names=['OUT共同倾斜','OUT共同曲率','OUT差分曲率','OUT髋膝速度倾斜','RETURN共同倾斜','RETURN共同曲率','RETURN差分曲率','RETURN髋膝速度倾斜']
probes=[]
for x in r['complete_evaluations']:
    if not x['id'].startswith('development_repair2_new_axis_'):continue
    tail=x['id'].split('new_axis_')[1];axis,sign=tail.split('_');axis=int(axis)
    probes.append(dict(id=x['id'],axis=axis,name=names[axis-10],normalized_value=float(sign)*.4,gain_percent=x['comparison']['gain_percent'],increment_over_prior_percent_points=x['comparison']['gain_percent']-prior['comparison']['gain_percent'],motion_pass=x['comparison']['acceptance_pass'],failures=x['comparison']['failed_requirements']))
phase=[]
regions=[]
for stage in ['QUALITY','ALTERNATE','REPAIR']:
    rr=[x for x in r['complete_evaluations'] if x['id'].startswith('development_repair2_') and x['candidate']['stage']==stage]
    if not rr:continue
    smooth=min(rr,key=lambda x:(x['constraints']['worst_ratio'],x['J_F_N_s']));low=min(rr,key=lambda x:x['J_F_N_s'])
    regions.append(dict(stage=stage,complete_physical_candidate_count=len(rr),motion_pass_count=sum(x['comparison']['acceptance_pass'] for x in rr),
                        least_worst_constraint_candidate=dict(id=smooth['id'],gain_percent=smooth['comparison']['gain_percent'],worst_ratio=smooth['constraints']['worst_ratio'],failed_requirements=smooth['comparison']['failed_requirements'],full_constraint_components=smooth['constraints']['components']),
                        lowest_force_candidate=dict(id=low['id'],gain_percent=low['comparison']['gain_percent'],motion_pass=low['comparison']['acceptance_pass'],failed_requirements=low['comparison']['failed_requirements'])))
for name in ['OUTBOUND','RETURN']:
    rr=[x for x in selected['free_execution'] if x['phase']==name]
    phase.append(dict(phase=name,metadata_plans=len(rr),phase_enabled_owned_plans=sum(x['richer_intent_owned_actual_steps'] for x in rr),phase_enabled_owned_native_steps=sum(x['actual_native_steps'] for x in rr if x['richer_intent_owned_actual_steps']),accepted_position_changes=[x['accepted_position_target_change_rad'] for x in rr if x['accepted_position_target_change_rad'] is not None],rejected_position_proposals=sum(x['position_proposal_status']=='REJECTED' for x in rr)))
with np.load(S/'source/results'/best['id']/'trace.npz') as a,np.load(S/'source/results'/best['base_id']/'trace.npz') as b:
    def last_indices(t):
        _,indices=np.unique(t[::-1],return_index=True);return np.sort(len(t)-1-indices)
    ia=last_indices(a['time_s']);ib=last_indices(b['time_s']);common,xa,xb=np.intersect1d(a['time_s'][ia],b['time_s'][ib],return_indices=True);assert len(common)>1
    actual_changes={key:float(np.max(abs(a[key][ia[xa]]-b[key][ib[xb]]))) for key in ['reference_q_rad','reference_dq_rad_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n']}
    alignment=dict(method='exact shared physical timestamps, last record for duplicate boundary; no interpolation',shared_sample_count=len(common),selected_unique_samples=len(ia),B_unique_samples=len(ib))
output=dict(status='COMPLETE',generated_unix=time.time(),physics_attempts_added=0,selected_id=best['id'],selected_parameters=best['candidate']['free_parameters'],selected_normalized_parameters=best['candidate']['normalized_parameters'],one_axis_matched_probes=probes,search_regions=regions,selected_phase_ownership=phase,selected_vs_B_max_abs_trace_changes=actual_changes,trace_alignment=alignment,
            attribution_limit='one-axis probes compare the old teacher with one added coordinate at ±0.4. The jointly optimized final gain is not an additive causal contribution or a final-parameter ablation. Accepted position target changes are explicit; rejected positions may still have velocity effects, so no automatic zero-actuation claim.',
            absolute_movement_truth='receipt ownership plus changed issued reference/torque and actual Human trace; global parameter nonzero alone is not proof')
(S/'MECHANISM_ANALYSIS.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
print('MECHANISM_ANALYSIS_COMPLETE',len(probes),phase,actual_changes)
