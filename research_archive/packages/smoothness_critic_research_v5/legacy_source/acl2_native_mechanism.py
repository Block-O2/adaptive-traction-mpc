"""Posthoc kinematics and nominal load-term accounting, zero native steps.

Signed projections add exactly under the original nominal allocation. They are
not independent physical doses or causal component-removal interventions.
"""
import os,sys,json,collections
import numpy as np
from acl2_shared import P,R,put,read,utc,sha
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,dynamic_regressor_row
from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

TERMS=['inertia','coriolis','gravity','passive_elastic','viscous_damping','soft_limit','state_residual']

def load(ident):
    f=R/'source/results'/ident/'trace.npz'
    with np.load(f) as z:
        ix=np.flatnonzero(z['stage']=='TASK')
        return dict(t=z['time_s'][ix],q=z['reference_q_rad'][ix],v=z['reference_dq_rad_s'][ix],a=z['reference_ddq_rad_s2'][ix],human=z['evaluation_only_human_state_rad_rad_s'][ix],force=z['physical_cuff_force_world_n'][ix],moment=z['physical_cuff_moment_world_nm'][ix],trace_sha256=sha(f))

def nominal(ident,model,allocator):
    d=load(ident);t=d['t'];components=[];maxerror=0.
    for q,v,a in zip(d['q'],d['v'],d['a']):
        reg=dynamic_regressor_row(q,v,np.zeros(2));beta=np.asarray(model.beta)
        torques=[model.mass_matrix(q)@a,reg[:,:3]@beta[:3],reg[:,3:5]@beta[3:5],reg[:,5:9]@beta[5:9],reg[:,9:11]@beta[9:11],-soft_limit_torque(q,v,model.rom_human),model.state_residual_nm(np.r_[q,v])]
        maxerror=max(maxerror,float(np.max(abs(sum(torques)-model.inverse_dynamics(q,v,a)))))
        A=allocator._prepare_factors(q,model).action_to_wrench_world
        components.append(np.stack([A@tau for tau in torques]))
    w=np.asarray(components);total=w.sum(axis=1);dt=np.diff(t);out={}
    for label,sl in [('force',slice(0,3)),('moment',slice(3,6))]:
        vec=total[:,sl];norm=np.linalg.norm(vec,axis=1);unit=vec/np.maximum(norm[:,None],1e-15);proj=np.einsum('nkj,nj->nk',w[:,:,sl],unit);contribution=proj[:-1].T@dt
        out[label]=dict(norm_integral=float(norm[:-1]@dt),signed_projection_integral_by_term={name:float(contribution[k]) for k,name in enumerate(TERMS)},additivity_error=float(abs(contribution.sum()-norm[:-1]@dt)))
    out['inverse_dynamics_sum_max_error_Nm']=maxerror;return out,d

def main():
    rows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()];D={r['id']:r for r in rows};base=D.get('CORE_STRONG')
    if base is None:return
    valid=[r for r in rows if r['qualified'] and not r['id'].startswith('LOCKED_') and r['action'].get('family')=='modal8_retimed']
    if not valid:return
    best=min(valid,key=lambda r:r['JF']);joint=[r for r in valid if r['JF']<base['JF']-.01 and r['JM']<base['JM']-.01];pareto=min(joint,key=lambda r:r['JF'],default=None)
    ids=list(dict.fromkeys([best['id']]+([pareto['id']] if pareto else [])+[i for i in ['CORE_B_017','CORE_C_017'] if i in D and D[i]['complete']]))
    belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json');geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});model=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']));allocator=CuffAwareSagittalAllocator();bn,bd=nominal(base['id'],model,allocator);data=[];plotdata={}
    for ident in ids:
        r=D[ident];n,d=nominal(ident,model,allocator);q0=np.column_stack([np.interp(d['t'],bd['t'],bd['q'][:,j]) for j in range(2)]);h0=np.column_stack([np.interp(d['t'],bd['t'],bd['human'][:,j]) for j in range(2)])
        counts=collections.Counter();reasons=collections.Counter();slot=[]
        for e in r.get('execution',[]):
            m=e.get('modal')
            if not m:continue
            key=m['phase']+'/'+m['status'];counts[key]+=1
            if m.get('reason'):reasons[m['reason']]+=1
            slot.append(dict(phase=m['phase'],slot=m.get('slot'),status=m['status'],activated=e.get('activated'),requested_duration_s=m['proposed_duration_s'],selected_duration_s=m.get('actually_selected_duration_s'),scheduler=m.get('scheduler_duration_record'),proposed_target_rad=m['proposed_target_rad'],selected_target_rad=m.get('actually_selected_target_rad')))
        delta={}
        for label in ['force','moment']:delta[label]=dict(nominal_norm_integral_delta=n[label]['norm_integral']-bn[label]['norm_integral'],signed_projection_delta_by_term={term:n[label]['signed_projection_integral_by_term'][term]-bn[label]['signed_projection_integral_by_term'][term] for term in TERMS})
        phases={ph:dict(deltaJF=r['phase_cost'][ph]['J_F_N_s']-base['phase_cost'][ph]['J_F_N_s'],deltaJM=r['phase_cost'][ph]['moment_integral_Nm_s']-base['phase_cost'][ph]['moment_integral_Nm_s'],duration_delta_s=r['phase_cost'][ph]['phase_clock_duration_s']-base['phase_cost'][ph]['phase_clock_duration_s']) for ph in ['OUTBOUND','HOLD','RETURN']}
        data.append(dict(id=ident,action=r['action'],qualified=r['qualified'],actual_JF=r['JF'],actual_JM=r['JM'],actual_phase_differences=phases,reference_q_change_min_max_deg=[np.degrees((d['q']-q0).min(0)),np.degrees((d['q']-q0).max(0))],actual_Human_q_change_min_max_deg=[np.degrees((d['human'][:,:2]-h0).min(0)),np.degrees((d['human'][:,:2]-h0).max(0))],slot_counts=dict(counts),rejection_reasons=dict(reasons),slot_records=slot,posthoc_nominal=n,posthoc_nominal_delta=delta,raw_trace_sha256=d['trace_sha256']))
        plotdata[ident]=(d,q0,h0)
    put('EXECUTED_COORDINATION_MECHANISMS.json',dict(utc=utc(),status='POSTHOC_ACCOUNTING',base_id=base['id'],base_actual_JF=base['JF'],base_actual_JM=base['JM'],base_nominal=bn,rows=data,new_native_steps=0,scope='Already-issued reference plus original causal commissioned model; not prospective performance, true Human dynamic-term identification or causal mediation. Signed force/moment projections sum algebraically under the nominal allocator; individual term values are not separate physical loads.',inertia_coriolis_gravity_elastic_damping_split='Exact original11-parameter regressor, soft-limit and bounded residual; no true patient model parameters accessed.',source_sha256=sha(__file__)))
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(2,2,figsize=(12,8));t0=bd['t'][0]
    for ident,(d,q0,h0) in plotdata.items():
        t=d['t']-t0;ax[0,0].plot(t,np.degrees(d['q'][:,0]-q0[:,0]),label=ident);ax[0,1].plot(t,np.degrees(d['q'][:,1]-q0[:,1]),label=ident)
        f0=np.interp(d['t'],bd['t'],np.linalg.norm(bd['force'],axis=1));m0=np.interp(d['t'],bd['t'],np.linalg.norm(bd['moment'],axis=1));ax[1,0].plot(t,np.linalg.norm(d['force'],axis=1)-f0,label=ident);ax[1,1].plot(t,np.linalg.norm(d['moment'],axis=1)-m0,label=ident)
    labels=['Actual issued hip reference change (deg)','Actual issued knee reference change (deg)','Measured force norm change (N)','Measured moment norm change (Nm)']
    for a,label in zip(ax.flat,labels):a.set(xlabel='Task time (s)',ylabel=label);a.legend(fontsize=6);a.grid(alpha=.2)
    fig.suptitle('Posthoc changes vs strong; original task/HOLD retained');fig.tight_layout();fig.savefig(P/'figures/EXECUTED_REFERENCE_AND_LOAD_CHANGES.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
