from common import *
import csv, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ruckig
def smooth(a,phases,t):
    def row(a):
        j=np.abs(np.diff(a,axis=0))
        return dict(n=len(a),max_adjacent_jump_per_joint=j.max(axis=0),max_adjacent_jump=j.max(),p95_jump_per_joint=np.percentile(j,95,axis=0),p99_jump_per_joint=np.percentile(j,99,axis=0),total_variation_per_joint=j.sum(axis=0),range_min=a.min(axis=0),range_max=a.max(axis=0),near_bound_coordinate_frequency=np.mean(abs(a)>=.95))
    return dict(full=row(a),per_phase={p:row(a[phases==p]) for p in np.unique(phases)},switch_region=row(a[(t>=1.35)&(t<=1.70)]))
def run():
    lock();z=np.load(DEMO);x=z['observations'];y=z['actions'];t=z['task_s'];ph=z['phase'];n=len(t)
    tr=task_trace(TEACHER);summary=json.loads((TEACHER/'summary.json').read_text());commands=[r for r in summary['online_reference_records'] if 'command_received_s' in r]
    assert len(commands)==n
    t0=float(np.median([r['command_received_s']-t[i] for i,r in enumerate(commands)]));tt=tr['time_s']-t0
    shutil.copy2(TEACHER/'trace.npz',O/'TEACHER_TRACE.npz')
    # Independent numeric reconstruction of source policy, using its actual causal inputs.
    raw=x.astype(float)*SCALES;target=raw[:,45:47].copy();mask=(ph=='OUTBOUND')&(t<1.5)
    target[mask,1]=np.minimum(target[mask,1],raw[mask,5]+.02)
    reconstructed=(2*target/np.radians(125.)-1).astype(np.float32)
    assert np.max(abs(reconstructed-y))<3e-7
    src=S/'scripts/single_human_sac_expert_v1/qualify.py'
    refs=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/online_reference.py'
    evidence=dict(source_path=src,source_sha256=sha(src),source_lines=[dict(line=i,text=line) for i,line in enumerate(src.read_text().splitlines(),1) if 'fixed_hip_lead' in line or "t<1.5" in line],variable='info[physics_task_s] (elapsed TASK time), info[phase], env.owned.q_rad[1], env.soft_target[1]',condition="phase == 'OUTBOUND' and t < 1.5",pre_target='min(soft_terminal_knee, owned_reference_knee+.02 rad)',post_target='soft_terminal_knee (120deg)',cause='fixed elapsed-task-time release of hip-leading knee clamp; no phase change, progress threshold, reference completion or hidden mode triggers it',observability='OBSERVABLE',actor_features=[41,44,45,46,5],clock_raw_s=[raw[74,44],raw[75,44]],clock_normalized=[x[74,44],x[75,44]],threshold_normalized=.05,phase=[ph[74],ph[75]],reconstruction_max_error=np.max(abs(reconstructed-y)),before_command=commands[74],switch_command=commands[75],otg_source_path=refs,OTG_C2_jumps=commands[75]['activation_validation']['jumps'],OTG_C2=commands[75]['activation_validation']['C2'],OTG_reference_effect_delay_s=commands[75]['reference_effect_latency_s'])
    save('SWITCH_SOURCE_TRACE.json',evidence)
    spec=feature_spec();rows=[]
    for f in spec:
        j=f['index'];d=x[75,j]-x[74,j];span=np.ptp(x[:,j]);std=np.std(x[:,j])
        rows.append(dict(**f,raw_74=raw[74,j],raw_75=raw[75,j],raw_delta=raw[75,j]-raw[74,j],normalized_74=x[74,j],normalized_75=x[75,j],normalized_delta=d,normalized_trajectory_range=span,delta_over_range=None if span==0 else abs(d)/span,delta_over_std=None if std==0 else abs(d)/std))
    save('OBSERVATION_DIMENSIONS.json',rows)
    with (O/'OBSERVATION_DIMENSIONS.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(clean(rows))
    dx=np.linalg.norm(x[:,None,:].astype(float)-x[None,:,:],axis=2);da=np.max(abs(y[:,None,:]-y[None,:,:]),axis=2);np.fill_diagonal(dx,np.inf)
    candidates=np.argwhere(np.triu((da>=.5),1));rank=sorted(candidates.tolist(),key=lambda ij:dx[tuple(ij)])[:50]
    pairs=[dict(i=i,j=j,time_i=t[i],time_j=t[j],phase_i=ph[i],phase_j=ph[j],observation_L2=dx[i,j],observation_RMS=dx[i,j]/np.sqrt(55),action_max_gap=da[i,j],actions=[y[i],y[j]],clock_gap_s=abs(t[j]-t[i]),previous_action_gap=x[j,49:51]-x[i,49:51]) for i,j in rank]
    nearest=dx.min(axis=1)
    save('NEAR_OBSERVATION_CONFLICTS.json',dict(action_difference_threshold=.5,top50=pairs,nearest_neighbor_L2_percentiles=np.percentile(nearest,[0,50,95,99,100]),switch_pair=dict(L2=dx[74,75],RMS=dx[74,75]/np.sqrt(55),relative_to_median_nearest=dx[74,75]/np.median(nearest)),interpretation='close observations with differing labels exist; explicit phase and clock distinguish the exact source switch. Proximity is evidence of sharp landscape, not non-observability or contradictory identical inputs. Entire single trajectory searched.'))
    concentration=[];predictions=[]
    for seed in read('PLAN_FROZEN.json')['seeds']:
        a=actor(seed);ck=torch.load(W/'bc_reproduction_gate_v1/output'/f'actor_seed_{seed}.pt',map_location='cpu',weights_only=True);a.load_state_dict(ck['state_dict']);a.eval()
        with torch.no_grad():pred=a(torch.tensor(x),deterministic=True).numpy()
        predictions.append(pred);e=pred-y;total=np.sum(e.astype(float)**2);windows={}
        for radius in (0,1,2,5):
            ids=np.arange(75-radius,76+radius);rest=np.setdiff1d(np.arange(n),ids)
            windows[str(radius)]=dict(indices=ids,window=error(pred[ids],y[ids]),SSE_fraction=np.sum(e[ids].astype(float)**2)/total,rest_of_trajectory=error(pred[rest],y[rest]))
        formal=json.loads((BC/f'OFFLINE_seed_{seed}.json').read_text())
        full=error(pred,y);assert abs(full['RMSE']-formal['metrics']['RMSE'])<1e-8
        concentration.append(dict(seed=seed,formal_full_data_metric=formal['metrics'],formal_offline_gate=formal['offline_pass'],recomputed_full_data=full,switch_prediction=pred[75],switch_target=y[75],switch_error=e[75],windows=windows,per_phase={p:error(pred[ph==p],y[ph==p]) for p in np.unique(ph)}))
        np.savez_compressed(O/f'EXACT_CURRENT_PREDICTIONS_seed_{seed}.npz',predictions=pred,teacher=y,error=e)
    save('CURRENT_BC_CONCENTRATION.json',concentration)
    # R2 is a fully causal bijection given existing previous-raw history; clipping is explicit.
    prev=x[:,49:51];delta=(y-prev)/2
    np.testing.assert_allclose(np.clip(prev+2*delta,-1,1),y,atol=1e-7)
    # R3 preview uses only current owned reference and current accepted teacher command.
    # Never use subsequent measured/physical state as labels.
    vmax=np.radians([45,75])*.5;amax=np.radians([300,600])*.25;jmax=amax/.020
    vel=[];preq=[];errors=[];schedule=None;epoch=None
    for i,cmd in enumerate(commands):
        ix=np.argmin(abs(tt-t[i]));assert abs(tt[ix]-t[i])<1e-7
        if cmd['status']=='ACCEPTED':
            inp=ruckig.InputParameter(2);inp.current_position=tr['reference_q_rad'][ix].tolist();inp.current_velocity=tr['reference_dq_rad_s'][ix].tolist();inp.current_acceleration=tr['reference_ddq_rad_s2'][ix].tolist()
            inp.target_position=cmd['target_rad'];inp.target_velocity=[0.,0.];inp.target_acceleration=[0.,0.];inp.max_velocity=vmax.tolist();inp.max_acceleration=amax.tolist();inp.max_jerk=jmax.tolist();inp.synchronization=ruckig.Synchronization.No
            schedule=ruckig.Trajectory(2);res=ruckig.Ruckig(2,.005).calculate(inp,schedule);assert res in (ruckig.Result.Working,ruckig.Result.Finished);epoch=t[i]
        assert schedule is not None
        q,v,acc=schedule.at_time(min(schedule.duration,t[i]-epoch+.020));vel.append(np.array(v)/vmax);preq.append(q)
        j=np.argmin(abs(tt-(t[i]+.020)))
        if abs(tt[j]-(t[i]+.020))<1e-7 and ph[i]==tr['task_phase'][j]:errors.append(np.max(abs(np.array(q)-tr['reference_q_rad'][j])))
    vel=np.array(vel);preq=np.array(preq)
    labels=dict(R1=y,R2=delta,R3=vel)
    np.savez_compressed(O/'REPRESENTATION_LABELS.npz',**labels,observations=x,phase=ph,task_s=t,velocity_preview_q_rad=preq)
    sm={k:smooth(v,ph,t) for k,v in labels.items()}
    # R2 physical units are delta targets; R1 physical units are targets. R3 has velocity units.
    sm['physical_units']=dict(R1_deg=smooth(62.5*(y+1),ph,t),R2_delta_deg=smooth(125.*delta,ph,t),R3_deg_s=smooth(vel*np.degrees(vmax),ph,t))
    definitions=dict(R1=dict(actor_output='absolute raw target a in[-1,1]^2',online='q_target=ROM*(a+1)/2; unchanged certified Ruckig state-to-state realization',causal=True,teacher_behavior_expressible=True,safety_preserved=True),R2=dict(actor_output='d=(a_teacher-a_previous_raw)/2 in[-1,1]^2',online='a_proposed=clip(previous_raw+2*d,-1,1); q_target=ROM*(a_proposed+1)/2; unchanged certified layer; previous_raw becomes proposed a even if rejected',causal=True,teacher_behavior_expressible=True,safety_preserved=True,initial_previous_raw='existing zero reset',fair_fit_eligible=True,caution='A target difference transfers the release into an impulse; its own adjacent variation can increase. Errors reported also in reconstructed absolute/degree units.'),R3=dict(actor_output='v_intent at t+.020 from currently accepted certified teacher continuation, normalized by[22.5,37.5]deg/s',online_candidate='Ruckig velocity-control tracking from current owned(q,dq,ddq), with explicit full stopping suffix and new certificate adapter; alternative short position target q_owned+.020*v requires testing and differs from source schedule',causal=True,label_sources='current owned reference, current accepted teacher command, current status, frozen OTG limits, known future duration; no future physical states',velocity_preview_reference_q_max_error_rad=max(errors),teacher_behavior_expressible='not established: local velocity preview discards long-range endpoint and stopped continuation; finite-preview velocity map is many-to-one under saturation',safety_preserved='not established by existing position-only interface: realize() fixes terminal dq/ddq=0 and certifies full endpoint continuation; velocity control needs a versioned adapter',fair_fit_eligible=False,fit_status='SKIPPED_NO_EQUIVALENT_DEPLOYABLE_SAFE_ADAPTER',reason='Fitting velocity labels would compare an output of the reference layer against its input and permit a lag/preview shortcut. Smoothness is descriptive only; no deployable equivalence or learnability superiority claim.'))
    save('REPRESENTATION_DEFINITIONS.json',definitions);save('REPRESENTATION_SMOOTHNESS.json',sm)
    win=(tt>=1.35)&(tt<=1.70);q=tr['evaluation_only_human_state_rad_rad_s'];ref=tr['reference_q_rad'];dq=tr['reference_dq_rad_s'];ddq=tr['reference_ddq_rad_s2']
    k=np.argmin(abs(tt-t[75]));before=max(0,k-1);after=min(len(tt)-1,k+1)
    continuity=dict(raw_knee_jump_deg=(y[75,1]-y[74,1])*62.5,raw_action_jump=y[75]-y[74],reference_C2_activation_jumps=commands[75]['activation_validation']['jumps'],switch_control_ticks_s=tt[before:after+1],reference_q_deg=np.degrees(ref[before:after+1]),reference_dq_deg_s=np.degrees(dq[before:after+1]),reference_ddq_deg_s2=np.degrees(ddq[before:after+1]),actual_q_deg=np.degrees(q[before:after+1,:2]),actual_dq_deg_s=np.degrees(q[before:after+1,2:]),window_max_adjacent_reference_q_deg=np.max(abs(np.diff(np.degrees(ref[win]),axis=0)),axis=0),window_max_adjacent_reference_dq_deg_s=np.max(abs(np.diff(np.degrees(dq[win]),axis=0)),axis=0),window_max_adjacent_reference_ddq_deg_s2=np.max(abs(np.diff(np.degrees(ddq[win]),axis=0)),axis=0),window_max_adjacent_actual_q_deg=np.max(abs(np.diff(np.degrees(q[win,:2]),axis=0)),axis=0),sampling_period_s=np.median(np.diff(tt[win])),interpretation='High-level target discontinuity; exact activation is C2 (q,dq,ddq). Subsequent acceleration changes are bounded by jerk. This proves immediate continuity, not closed-loop equivalence when a policy misses the release.')
    save('SWITCH_CONTINUITY.json',continuity)
    fig,axs=plt.subplots(7,1,figsize=(12,18),sharex=True)
    pw=(t>=1.35)&(t<=1.70)
    for j,name in enumerate(('hip','knee')):
        axs[0].plot(t[pw],y[pw,j],label='teacher '+name,marker='o',markersize=3)
        for seed,pred in zip(read('PLAN_FROZEN.json')['seeds'],predictions):axs[0].plot(t[pw],pred[pw,j],label=f'BC{seed} {name}',alpha=.7)
        axs[1].plot(tt[win],np.degrees(ref[win,j]),label=name)
        axs[2].plot(tt[win],np.degrees(dq[win,j]),label=name)
        axs[3].plot(tt[win],np.degrees(ddq[win,j]),label=name)
        axs[4].plot(tt[win],np.degrees(q[win,j]),label='actual '+name)
        axs[4].plot(tt[win],np.degrees(tr['estimated_human_state_rad_rad_s'][win,j]),'--',label='estimated '+name)
        axs[5].plot(tt[win],np.degrees(q[win,j+2]),label=name)
    progress=np.min(np.clip((raw[:,:2]-np.radians([5,10]))/np.radians([115,110]),0,1),axis=1)
    axs[6].plot(t[pw],progress[pw],label='sync progress');axs[6].plot(t[pw],x[pw,41],label='OUTBOUND');axs[6].plot(t[pw],(t[pw]<1.5).astype(float),label='knee clamp active');axs[6].plot(t[pw],t[pw]/1.5,label='elapsed / threshold')
    for ax,label in zip(axs,('raw absolute actions','reference q (deg)','reference dq (deg/s)','reference ddq (deg/s2)','actual Human q (deg)','actual Human dq (deg/s)','phase / progress / trigger')):
        ax.set_ylabel(label);ax.axvline(1.5,color='k',linestyle=':');ax.grid(alpha=.2);ax.legend(fontsize=7,ncol=3)
    axs[-1].set_xlabel('TASK elapsed time (s)');fig.tight_layout();fig.savefig(O/'SWITCH_ZOOM.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True)
    for ax,(name,a) in zip(axs,labels.items()):
        ax.plot(t,a[:,0],label='hip');ax.plot(t,a[:,1],label='knee');ax.set_ylabel(name);ax.axvline(1.5,color='k',ls=':');ax.legend();ax.grid(alpha=.2)
    axs[-1].set_xlabel('TASK elapsed (s)');fig.tight_layout();fig.savefig(O/'REPRESENTATIONS.png',dpi=160);plt.close(fig)
    save('STATE.json',dict(status='OFFLINE_COMPLETE',next='three autonomous diagnostic BC replays'))
    print(json.dumps(clean(dict(status='OFFLINE_COMPLETE',trigger=evidence['condition'],C2=evidence['OTG_C2'],raw_jump_deg=continuity['raw_knee_jump_deg'],R3_preview_error=max(errors),representation_max_jumps={k:sm[k]['full']['max_adjacent_jump'] for k in labels}))),flush=True)
if __name__=='__main__':run()
