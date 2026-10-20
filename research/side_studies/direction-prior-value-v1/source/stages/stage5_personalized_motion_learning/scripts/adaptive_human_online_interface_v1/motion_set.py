"""Identical deterministic target-intention streams through old/new realizations."""
from online_probes import *
from collections import Counter
def main():
    rows=[]
    for condition in ('sync_120','low_ordinary_early'):
        case,spec,b,c,artifact=context(condition);lim=limits(spec)
        for phase in ('OUTBOUND','RETURN'):
            goal=np.array(spec.outbound_goal_target_rad if phase=='OUTBOUND' else spec.start_return_target_rad);old=original(artifact,phase,goal)
            at=old.sample(min(.2,old.duration_s/2));state=(at.q_rad,at.dq_rad_s,at.ddq_rad_s2);seed=realize(state,old.candidate.q_waypoint_rad,spec=spec,phase=TaskPhase(phase),**lim)
            for period in (.005,.01,.02,.05):
                for pattern in ('identical','switch','reverse_alternating'):
                    owner=OnlineReferenceOwner(state,initial_schedule=seed)
                    commands=[];path=[];original_end=old.duration_s-min(.2,old.duration_s/2)
                    for k in range(int(round(.5/period))+1):
                        t=k*period
                        if pattern=='identical':target=seed.candidate.q_waypoint_rad
                        elif pattern=='switch':target=at.q_rad+([.08,.03] if int(t/.1)%2==0 else [.03,.08])
                        else:target=at.q_rad+([.06,.02] if int(t/.1)%2==0 else [-.015,-.01])
                        target=np.maximum(np.asarray(spec.q_bounds_rad)[:,0],np.minimum(np.asarray(spec.q_bounds_rad)[:,1],target))
                        before=owner.sample(t)
                        record=owner.offer(target,received_s=t,ready_s=t,requested_s=t,spec=spec,phase=TaskPhase(phase),remaining_s=spec.phase_timeout_s-t,belief=b,clearance=c,**lim)
                        after=owner.sample(t)
                        jumps=[np.max(abs(x-y)) for x,y in zip((before.q_rad,before.dq_rad_s,before.ddq_rad_s2),(after.q_rad,after.dq_rad_s,after.ddq_rad_s2))]
                        if max(jumps)>1e-10:raise AssertionError('non-C2 active handoff')
                        commands.append(record);s=owner.sample(t+period);path.append(s.q_rad.tolist())
                    latencies=[x['reference_effect_latency_s'] for x in commands if x.get('reference_effect_latency_s') is not None]
                    q=np.array(path);delta=q-q[0];lead=delta[:,0]-delta[:,1]
                    # OLD: original endpoint-bound RSS cannot activate before its owned endpoint.
                    old_deferred=[max(0.,original_end-x['command_received_s']) for x in commands]
                    rows.append(dict(condition=condition,phase=phase,period_s=period,pattern=pattern,command_count=len(commands),new_status_counts=dict(Counter(x['status'] for x in commands)),new_reference_effect_latency_s=latencies,new_latency_min_s=min(latencies) if latencies else None,new_latency_max_s=max(latencies) if latencies else None,old_initial_endpoint_s=original_end,old_endpoint_deferred_fraction=float(np.mean(np.array(old_deferred)>0.)),old_minimum_deferral_s=min(old_deferred),new_path_q_rad=q.tolist(),lead_min_rad=float(min(lead)),lead_max_rad=float(max(lead)),realized_lead_sign_change=bool(min(lead)<-1e-5 and max(lead)>1e-5),new_commands=commands,physical_force_moment='not measured in this reference-only comparison; see separate CR12 runs'))
    save('MOTION_SET_COMPARISON.json',dict(scope='deterministic reference and activation safety; old endpoint comparator is reconstructed, not a new physical rollout',rows=rows))
    print(json.dumps({'motion_streams':len(rows),'changed_commands':sum(x['new_status_counts'].get('ACCEPTED',0) for x in rows),'streams_with_lead_sign_changes':sum(x['realized_lead_sign_change'] for x in rows)}))
if __name__=='__main__':main()
