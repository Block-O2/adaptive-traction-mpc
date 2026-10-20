"""Offline evidence extraction. No simulator/runtime/controller imports or calls.

Registered plant truth is used only for retrospective analytic coefficients.
Incomplete patients remain present; no gates are changed or inferred.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
import numpy as np

NAMES = ['a_inertia_combination','b_distal_inertia_combination',
 'd_mass_length_com_combination','g1_proximal_gravity_combination',
 'g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness',
 'rho1_stiffness_rest_combination','rho2_stiffness_rest_combination',
 'bv1_viscous_damping','bv2_viscous_damping']

def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x): return None
    return x

def truth_parameters(physical):
    h=physical['height_m'];m=physical['body_mass_kg']
    l1=.254*h*physical['thigh_length_scale'];l2=.233*h*physical['shank_length_scale']
    m1=.099*m*physical['thigh_mass_scale'];m2=.060*m*physical['shank_mass_scale']
    c1=l1*physical['thigh_com_fraction'];c2=l2*physical['shank_com_fraction']
    i1=m1*(physical['thigh_inertia_radius_fraction']*l1)**2
    i2=m2*(physical['shank_inertia_radius_fraction']*l2)**2
    b=i2+m2*c2*c2;d=m2*l1*c2;a=i1+m1*c1*c1+b+m2*l1*l1
    k=np.array(physical['passive_stiffness_nm_rad']);rest=np.deg2rad(physical['q_rest_deg'])
    beta=np.r_[a,b,d,9.81*(m1*c1+m2*l1),9.81*m2*c2,k,k*rest,physical['passive_damping_nms_rad']]
    return {'usage':'OFFLINE_EVALUATION_ONLY_NOT_CONTROLLER_INPUT','base_parameter_names':NAMES,
      'beta':beta,'resolved':dict(l1_m=l1,l2_m=l2,m1_kg=m1,m2_kg=m2,c1_m=c1,c2_m=c2,
      I1_kg_m2=i1,I2_kg_m2=i2,knee_to_cuff_m=l2*physical['cuff_fraction_of_shank']),
      'effective_geometry':[physical['hip_translation_xz_m'][0],.062+physical['hip_translation_xz_m'][1],l1,l2*physical['cuff_fraction_of_shank']]}

def extract(package):
    package=Path(package).resolve();sources={};warnings=[]
    def record(rel):
        path=package/rel
        sources[rel]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        return path
    def read(rel,default=None):
        if not (package/rel).exists(): return default
        return json.loads(record(rel).read_text())
    cohort=read('VIRTUAL_PATIENT_COHORT.json');rows=[]
    for patient in cohort['patients']:
        pid=patient['patient_id'];pair=read(pid+'_COMPARISON.json')
        truth=truth_parameters(patient['physical'])
        out={'patient_id':pid,'label':patient['label'],'truth_offline_only':truth,
             'pair_available':pair is not None,'arms':{}}
        if pair is None:
            out['status']='NO_COMPLETED_PAIR';rows.append(out);continue
        done=read(pid+'_DONE.json',{});owner=read('audit/'+pid+'_OWNER.json',{})
        out['joined_before_extraction']=bool(done.get('all_children_joined') and owner.get('joined'))
        if not out['joined_before_extraction']:
            out['status']='PAIR_EXISTS_WAITING_FOR_JOIN';rows.append(out);continue
        out.update({k:pair.get(k) for k in ['gain_percent','motion_relative','full_integral_comparison_valid','complete_qualified_H150']})
        out['motion_comparison']=pair.get('H150',{}).get('motion_comparison')
        for arm in ('B','H150'):
            ident=pid+'_'+arm;ev=pair.get(arm,{})
            measured=read('reports/'+ident+'_MEASURED.json',{})
            summary=read('source/results/'+ident+'/summary.json',{})
            receipts=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json',{})
            commissioning=summary.get('commissioning',{});belief=commissioning.get('handoff_belief',{})
            fit=commissioning.get('geometry_fit',{})
            beta=np.array(belief.get('beta',[]));truth_beta=np.array(truth['beta'])
            est_geometry=[*fit.get('hip_xz_m',[]),fit.get('thigh_length_m'),fit.get('knee_to_cuff_m')]
            ar={'qualification':ev.get('qualification'),'axes':ev.get('axes'),
                'motion_extra':ev.get('motion_extra'),'phase_cost':ev.get('phase_cost'),
                'phase_durations':ev.get('phase_durations'),'interventions':ev.get('interventions'),
                'measured':{k:measured.get(k) for k in ['J_F_N_s','moment_integral_Nm_s','force_peak_N','moment_peak_Nm','tracking_RMS_deg']},
                'dose':{k:measured.get('dose',{}).get(k) for k in ['excursion_deg','endpoint_deg']},
                'commissioning':{'duration_s':commissioning.get('duration_s'),
                 'sample_count':commissioning.get('sample_count'),'geometry_fit':fit,
                 'handoff_belief':belief,'population_beta_initial':commissioning.get('population_beta_initial'),
                 'measured_handoff_beta_matches_summary':measured.get('commissioning',{}).get('model_beta')==belief.get('beta'),
                 'effective_reference_waypoints_deg':np.rad2deg(commissioning.get('effective_reference_waypoints_rad',[])),
                 'beta_minus_offline_truth':beta-truth_beta if beta.shape==(11,) else None,
                 'beta_relative_error_percent':100*(beta/truth_beta-1) if beta.shape==(11,) else None,
                 'geometry_minus_offline_truth_m':np.array(est_geometry)-truth['effective_geometry'] if len(est_geometry)==4 and all(v is not None for v in est_geometry) else None},
                'receipt_status':receipts.get('status')}
            native_rel='motion_series/'+ident+'.npz';trace_rel='source/results/'+ident+'/trace.npz'
            if not (package/native_rel).exists() or not (package/trace_rel).exists():
                ar['native_status']='MISSING';out['arms'][arm]=ar;continue
            with np.load(record(native_rel),allow_pickle=False) as z:
                mask=z['phase']=='RETURN';nt=z['time_s'][mask];nq=np.rad2deg(z['true_q_rad'][mask]);nv=np.rad2deg(z['true_dq_rad_s'][mask])
            with np.load(record(trace_rel),allow_pickle=False) as z:
                mask=(z['stage']=='TASK')&(z['task_phase']=='RETURN')
                tt=z['time_s'][mask];ref=np.rad2deg(z['reference_q_rad'][mask]);rv=np.rad2deg(z['reference_dq_rad_s'][mask])
                force=z['physical_cuff_force_world_n'][mask];moment=z['physical_cuff_moment_world_nm'][mask]
                tq=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,:2])
                tv=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,2:])
            origin=float(nt[0]);end=float(nt[-1]);extrema=[];plateaus=[]
            for j in range(2):
                ni=int(np.argmin(nq[:,j]));ti=int(np.argmin(abs(tt-nt[ni])))
                extrema.append({'joint':['hip','knee'][j],'minimum_deg':nq[ni,j],
                    'physics_time_s':nt[ni],'return_elapsed_s':nt[ni]-origin,
                    'true_q_deg_at_minimum':nq[ni],'true_dq_deg_s_at_minimum':nv[ni],
                    'nearest_trace_time_offset_s':tt[ti]-nt[ni],
                    'issued_reference_deg_nearest_trace':ref[ti],
                    'issued_reference_velocity_deg_s_nearest_trace':rv[ti],
                    'cuff_force_norm_N_nearest_trace':np.linalg.norm(force[ti]),
                    'cuff_moment_norm_Nm_nearest_trace':np.linalg.norm(moment[ti])})
                constant=(abs(ref[:,j]-ref[-1,j])<=1e-8)&(abs(rv[:,j])<=1e-7)
                differing=np.flatnonzero(~constant);start=int(differing[-1]+1) if len(differing) else 0
                if start>=len(tt):plateaus.append(None);continue
                nm=nt>=tt[start]-1e-10
                plateaus.append({'joint':['hip','knee'][j],'start_physics_s':tt[start],
                    'start_return_elapsed_s':tt[start]-origin,'reference_deg':ref[-1,j],
                    'sample_count':len(tt)-start,'reference_peak_to_peak_deg':np.ptp(ref[start:,j]),
                    'reference_max_abs_velocity_deg_s':np.max(abs(rv[start:,j])),
                    'true_joint_min_deg':np.min(nq[nm,j]),'true_joint_max_deg':np.max(nq[nm,j]),
                    'true_joint_peak_to_peak_deg':np.ptp(nq[nm,j]),
                    'true_joint_max_abs_velocity_deg_s':np.max(abs(nv[nm,j])),
                    'true_joint_rms_reference_error_deg':np.sqrt(np.mean((nq[nm,j]-ref[-1,j])**2))})
            owned=[r for r in receipts.get('rows',[]) if r.get('phase')=='RETURN' and r.get('actual_native_steps',0)>0]
            last=max(owned,key=lambda r:r['first_execution_physics_s']) if owned else None
            last_summary=None
            if last:
                rr=last['actual_command_receipts'];qr=np.rad2deg([r['q_ref_rad'] for r in rr]);vr=np.rad2deg([r['dq_ref_rad_s'] for r in rr])
                last_summary={'decision_index':last['decision_index'],'request_id':last['request_id'],
                    'first_execution_physics_s':last['first_execution_physics_s'],
                    'first_execution_return_elapsed_s':last['first_execution_physics_s']-origin,
                    'last_receipt_end_physics_s':max(r['end_physics_s'] for r in rr),
                    'receipt_count':len(rr),'native_steps':last['actual_native_steps'],
                    'activation_outcome':last.get('activation_outcome'),
                    'q_reference_start_deg':qr[0],'q_reference_end_deg':qr[-1],
                    'q_reference_peak_to_peak_deg':np.ptp(qr,axis=0),
                    'dq_reference_max_abs_deg_s':np.max(abs(vr),axis=0)}
            local=tt>=end-3.5
            ar['return_evidence']={'origin_physics_s':origin,'end_physics_s':end,
                'native_duration_s':end-origin,'native_extrema':extrema,'final_reference_plateaus':plateaus,
                'last_return_receipt_group':last_summary,
                'last_3p5s_trace_diagnostic':{'start_physics_s':tt[local][0],
                    'force_mean_N':np.mean(np.linalg.norm(force[local],axis=1)),
                    'moment_mean_Nm':np.mean(np.linalg.norm(moment[local],axis=1)),
                    'tracking_RMS_deg':np.sqrt(np.mean((tq[local]-ref[local])**2,axis=0)),
                    'definition':'unweighted 5ms trace mean/RMS in final3.5s; not official J_F or a new gate'}}
            out['arms'][arm]=ar
        out['same_commissioning_belief_B_H150']=out['arms'].get('B',{}).get('commissioning',{}).get('handoff_belief')==out['arms'].get('H150',{}).get('commissioning',{}).get('handoff_belief')
        rows.append(out)
    source_files=['control/terminal_planner.py','code/analyze_matched.py',
     'source/stages/stage3_full3d/src/traction_mpc_stage3/human.py',
     'source/stages/stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py',
     'source/stages/stage4_adaptive_control/src/traction_mpc_stage4/estimator_v2.py',
     'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/effective_model.py',
     'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py',
     'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py']
    for rel in source_files:
        if (package/rel).exists():record(rel)
    return clean({'schema':'IHEAR_OFFLINE_MECHANISM_EVIDENCE_V1','generated_utc':datetime.now(timezone.utc).isoformat(),
        'physics_starts':0,'simulator_imports':False,'truth_use':'retrospective reporting only; never written to controller data',
        'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sources':sources,'patients':rows,'warnings':warnings})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True);parser.add_argument('--mirror',type=Path)
    args=parser.parse_args();data=extract(args.package);out=args.package/'audit_human'/'MECHANISM_EVIDENCE.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if args.mirror:
        args.mirror.mkdir(parents=True,exist_ok=True);shutil.copy2(out,args.mirror/out.name)
    print(json.dumps({'output':str(out),'joined_pairs_extracted':[r['patient_id'] for r in data['patients'] if r.get('joined_before_extraction')],'physics_starts':0}))

if __name__=='__main__':main()
