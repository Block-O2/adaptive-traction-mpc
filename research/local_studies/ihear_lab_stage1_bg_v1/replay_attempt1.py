"""Offline BG-1. Historical receipts authenticate sources; prospective samples never write."""
from pathlib import Path
from collections import Counter, defaultdict
from types import SimpleNamespace
from dataclasses import replace
from time import perf_counter_ns as tick
import hashlib, sys, json, platform, os
import numpy as np

HERE=Path(__file__).resolve().parent
RT2=HERE.parent/'ihear_lab_stage1_rt2_v1'
sys.path.insert(0,str(RT2))
import software_aligned as rt2
from env_rt2 import read, sha
from governor import H, desired, force_pair, sample, clock, allowance, project
from traction_mpc_stage5.full3d_adaptive_integration_v1.applied_reference_history import AppliedReferenceMotionHistory
from traction_mpc_stage5.full3d_adaptive_integration_v1.receipt_reference_governor import ReceiptReferenceGovernor
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22

def jets(x):
    return np.r_[x.q_rad,x.dq_rad_s,x.ddq_rad_s2]

class AnalyticContinuation:
    """Prospective full remainder from owned boundary, including reserved recovery."""
    continuous_clearance_certificate=None

    def __init__(self, path, start, a0, a1):
        self.path=path
        self.start=start
        self.a0=a0
        self.a1=a1
        self.mid=clock(start,a0,a1,H)[0]
        self.end=clock(self.mid,a1,1.,H)[0]
        if self.end>path.duration_s:
            raise ValueError('recovery crosses endpoint')
        self.duration_s=2*H+(path.duration_s-self.end)
        self.candidate=path.candidate

    def sample(self,t):
        if not 0<=t<=self.duration_s:
            raise ValueError('outside continuation')
        if t<=H: return sample(self.path,self.start,self.a0,self.a1,t)
        if t<=2*H: return sample(self.path,self.mid,self.a1,1.,t-H)
        if t==self.duration_s: return self.path.sample(self.path.duration_s)
        return self.path.sample(self.end+(t-2*H))

def main():
    rt2.BASE=RT2/'B/native'
    artifacts=read(rt2.BASE/'runtime_artifacts.json')
    receipts=artifacts['wall_physics']['command_receipts']
    by_time={round(r['source_sample_time_s'],7):j for j,r in enumerate(receipts) if r.get('reference_progress')}
    trace={round(r['time_s'],7):r for r in artifacts['trace'] if r['stage']=='TASK'}
    archived={(r['i'],r['k']):r for r in read(RT2/'software_aligned.json')['rows'] if r['kind']=='I'}
    frozen=read(RT2/'FREEZE.json')['sha']
    assert all(sha(rt2.ROOT/f)==v for f,v in frozen.items())
    baseline_belief=read(rt2.BASE/'summary.json')['commissioning']['handoff_belief']
    origin=(Path(__file__).resolve().parents[4] / 'adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3/key_traces/historical_B/summary.json')
    assert baseline_belief==read(origin)['commissioning']['handoff_belief']
    rows=[]; times=defaultdict(list); probes=[]; owners={}; prepared={}; max_c2=0.
    def timed(name,fn,*args):
        t=tick()
        try: return fn(*args)
        finally: times[name].append((tick()-t)/1e6)
    for i,k,path,s,planner,decision,e in rt2.reconstruct():
        d=artifacts['task_decisions'][i]
        old=archived[i,k]
        assert old['physical_stamp']==e['stamp'] and old['s']==s
        t=e['stamp']; j=by_time[round(t,7)]; r=receipts[j]; progress=r['reference_progress']
        tr=trace[round(t,7)]
        assert r['applied'] and r['supervisor_mode']=='TRACK' and r['validation_model_version']=='belief_351'
        assert np.array_equal(e['wrench'][:3],tr['cuff_force_world_n']) and np.array_equal(e['x'],tr['estimated_state'])
        assert tr['belief_sequence']==baseline_belief['sequence'] and np.array_equal(tr['residual_weights_nm'],baseline_belief['state_residual_weights_nm'])
        if i not in owners:
            prepared[i]=prepare_decision(decision,planner,e['belief']).executed.schedule
            rc=d['rolling_composite']
            owners[i]=RollingSuffixCompositeSchedule(prepared[i-1].safe_escape.bridge,rc['prefix_start_progress_s'],prepared[i],rc['request_id']) if rc else prepared[i]
        owner=owners[i]
        history_rows=receipts[j-6:j]; first=history_rows[0]
        hist=AppliedReferenceMotionHistory(lambda:t,first['q_ref_rad'],first['dq_ref_rad_s'],first['start_physics_s'])
        for x in history_rows[1:]: hist.commit_applied(x['start_physics_s'],x['q_ref_rad'],x['dq_ref_rad_s'])
        gov=ReceiptReferenceGovernor()
        gov.schedule=owner;gov.progress_s=progress['previous_progress_s']
        ref,prop=gov.select(owner,progress['desired_progress_s'],hist,e['spec'].task_joint_acceleration_limit_rad_s2)
        assert prop['selected_progress_s']==progress['selected_progress_s']
        assert np.allclose(prop['lower_dq_rad_s'],progress['lower_dq_rad_s'],atol=1e-10,rtol=0)
        assert np.allclose(prop['upper_dq_rad_s'],progress['upper_dq_rad_s'],atol=1e-10,rtol=0)
        err=max(abs(jets(ref)-np.r_[r['q_ref_rad'],r['dq_ref_rad_s'],tr['ddq_ref_rad_s2']]))
        max_c2=max(max_c2,err);assert err<=1e-10
        gov.commit(owner,prop,r)
        row=dict(i=i,k=k,phase=old['phase'],receipt=r['receipt_index'],owner=d['timing_request_id'],
                 version=owner.version,source=t,capture=r['source_capture_ns'],apply=r['apply_ns'],
                 sigma=s,original=old['reason'],identity_error=err)
        rows.append(row)
        if old['reason']=='native ownership':
            row['status']='HOLD' if old['phase']=='HOLD' else 'original endpoint'
            continue
        assert e['valid'] and prop['delay_added_s']==0.
        assert t==r['start_physics_s']
        model=e['belief'].human_model()
        pair=timed('two_model_calls',force_pair,model,e['x'][:2],e['owned'],1.)
        g,target=timed('law',desired,tr['cuff_force_world_n'],pair,1.)
        row.update(g=g,desired=target,force_norm=float(np.linalg.norm(e['wrench'][:3])),
                   D_norm=float(np.linalg.norm((pair[0]-pair[1])/.001)),
                   speed_ratio=float(max(abs(ref.dq_rad_s)/e['vmax'])),
                   accel_ratio=float(max(abs(ref.ddq_rad_s2)/e['amax'])))
        # Forecast unit advancement conditionally, inspecting only the owned
        # suffix and velocity-box/history at the speculative 5 ms boundaries.
        before=tick()
        hist.commit_applied(t,ref.q_rad,ref.dq_rad_s)
        boundary=s+H
        for step in range(1,9):
            now=t+.005*step
            hist.clock=lambda:now
            next_ref,proposal=gov.select(owner,prop['selected_progress_s']+.005*step,hist,e['spec'].task_joint_acceleration_limit_rad_s2)
            if proposal['delay_added_s']>0:break
            gov.progress_s=proposal['selected_progress_s'] # forecast object only
            hist.commit_applied(now,next_ref.q_rad,next_ref.dq_rad_s)
        times['forecast'].append((tick()-before)/1e6)
        if proposal['delay_added_s']>0:row['status']='receipt carry';continue
        # Current decision's original terminal target is already committed.
        if np.array_equal(path.candidate.q_waypoint_rad,d['terminal_reference_selection']['reference_target_rad']):
            row['status']='terminal waypoint';continue
        if any(np.all(axis[1:]==0) for axis in path.coefficients):
            row['status']='held axis';continue
        if boundary+2*H>path.duration_s:
            row['status']='room';continue
        row['predicted_boundary']=boundary
        try:
            delta,bounds=timed('continuous_allowance',allowance,path,boundary,e['vmax'],e['amax'])
            row['alpha']=timed('project',project,target,1.,delta)
            a1=project(.99,1.,delta)
        except ValueError as exc:
            row['status']=str(exc);continue
        row.update(fixture=a1,delta=float(delta),bounds=bounds)
        row['status']='unchanged' if row['alpha']==1 else 'no native certificate'
        if a1==1:continue
        view=AnalyticContinuation(path,boundary,1.,a1)
        mid=timed('analytic_sample',view.sample,H)
        true_mid=path.sample(boundary+H)
        row['fixture_dq']=max(abs(mid.q_rad-true_mid.q_rad));row['start_a']=max(abs(view.sample(0.).ddq_rad_s2))
        row['closure_degrees']=[4*max(np.nonzero(axis)[0],default=0) for axis in path.coefficients]
        if len(probes)<1 or (row['phase']=='RETURN' and len(probes)==1):
            x0=view.sample(0.)
            probe=dict(receipt=r['receipt_index'],phase=row['phase'],boundary=boundary,
                       start_q=x0.q_rad,start_v=x0.dq_rad_s,start_a=x0.ddq_rad_s2,end_lag=path.duration_s+2*H-boundary-(view.end-boundary)-path.duration_s)
            probe['mechanics']=timed('fixture_mechanics',AdaptiveMechanicsScreenV22().evaluate,e['belief'],view.candidate,view)
            begin=tick()
            try:
                out=validate_activation(belief=e['belief'],request_sequence=e['sequence'],schedule=view,
                    clearance=e['clearance'],phase=e['phase'],request_phase=e['phase'],
                    remaining_s=e['remaining']-H,reference_state=np.r_[x0.q_rad,x0.dq_rad_s])
                probe['admission']=out['feasible']
            except AttributeError as exc:probe['native_block']=str(exc)
            times['native_failed_precheck'].append((tick()-begin)/1e6)
            # C2 joins for successive proposals and for an unmodified scheduled recovery.
            follow=AnalyticContinuation(path,view.mid,a1,a1)
            follow2=AnalyticContinuation(path,follow.mid,a1,1.)
            probe['joins']=[max(abs(jets(mid)-jets(follow.sample(0.)))),
                max(abs(jets(follow.sample(H))-jets(follow2.sample(0.)))),
                max(abs(jets(view.sample(2*H))-jets(path.sample(view.end))))]
            probes.append(probe)
    assert len(rows)==len(archived)==392 and sum('g' in r for r in rows)==343
    meta=dict(sha_verified=len(frozen),zero_steps_guard='software_aligned.forbidden',max_identity_error=max_c2,
              cpu=list(os.sched_getaffinity(0)),python=platform.python_version(),numpy=np.__version__,
              trace_hash=sha(rt2.BASE/'trace.npz'),artifact_hash=sha(rt2.BASE/'runtime_artifacts.json'))
    rt2.save(HERE/'replay.json',dict(meta=meta,rows=rows,times=times,probes=probes))
    print(meta,Counter(r['status'] for r in rows))
if __name__=='__main__':main()
