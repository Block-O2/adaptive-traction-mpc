"""Offline goal-box/velocity diagnostics of saved evaluations. Never imports SAC."""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1/source');S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/demo_assisted_sac_task_acquisition_v1';L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1/output')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    task=S/'configs/high_rom_v1/stage5_goal_task_120_v1.json';cfg=json.loads(task.read_text())
    goal=np.asarray(cfg['outbound_goal_target_deg']);pt=np.asarray(cfg['joint_angle_completion_tolerance_deg']);vt=np.asarray(cfg['joint_velocity_completion_tolerance_deg_s'])
    previous=D/'OUTBOUND_SETTLING_AUDIT.json';rows=json.loads(previous.read_text()).get('rows',{}) if previous.exists() else {}
    for p in sorted(D.glob('EVALUATION_*.json')):
        r=json.loads(p.read_text());path=R/r['trace'];key=r['rollout_id']
        if not path.exists():continue
        assert sha(path)==r['trace_sha256']
        with np.load(path) as z:
            mask=z['stage']=='TASK';t=z['time_s'][mask]
            holds=[e['time_s'] for e in r['phase_transitions'] if e.get('to')=='HOLD']
            ob=t<=holds[0]+1e-9 if holds else np.ones(len(t),bool)
            q=np.degrees(z['estimated_human_state_rad_rad_s'][mask][ob,:2]);dq=np.degrees(z['estimated_human_state_rad_rad_s'][mask][ob,2:4])
            rq=np.degrees(z['reference_q_rad'][mask][ob]);rdq=np.degrees(z['reference_dq_rad_s'][mask][ob]);tt=t[ob]-t[0]
        err=np.abs(q-goal);pos=(err<=pt+1e-9).all(1);vel=(np.abs(dq)<=vt+1e-9).all(1);both=pos&vel
        closest=int(err.max(1).argmin());rzero=(np.abs(rq-goal)<=pt+1e-9).all(1)&(np.abs(rdq)<=1e-6).all(1)
        with np.load(path.parent/'SAC_ACTOR_ACTIONS.npz') as z:
            raw=z['raw_action'];late=raw[max(0,len(raw)-50):];target=62.5*(late+1)
        rows[key]=dict(arm=r['arm'],training_step=r['training_step'],scope=r['scope'],tag=r['tag'],trace=str(path),trace_sha256=r['trace_sha256'],termination=r['termination_reason'],max_synchronized_position_progress=r['max_synchronized_OUTBOUND_progress'],entered_HOLD=r['entered_HOLD'],independent_VALID=r['independent_VALID'],position_box_samples=int(pos.sum()),position_and_velocity_samples=int(both.sum()),position_velocity_and_zero_reference_proxy_samples=int((both&rzero).sum()),closest_max_joint_goal_error_deg=float(err[closest].max()),closest_goal_sample=dict(task_s=float(tt[closest]),q_deg=q[closest].tolist(),dq_deg_s=dq[closest].tolist(),reference_q_deg=rq[closest].tolist(),reference_dq_deg_s=rdq[closest].tolist()),final_q_deg=q[-1].tolist(),final_dq_deg_s=dq[-1].tolist(),final_reference_q_deg=rq[-1].tolist(),final_reference_dq_deg_s=rdq[-1].tolist(),last50_policy_target_mean_deg=target.mean(0).tolist(),last50_policy_target_range_deg=[target.min(0).tolist(),target.max(0).tolist()],last50_near_bound_action_rate=float((np.abs(late)>=.95).any(1).mean()))
    output=dict(status='OFFLINE_DIAGNOSTIC_NOT_A_NEW_SUCCESS_RULE',task_source_sha256=sha(task),actual_task_tolerances=dict(position_deg=pt.tolist(),velocity_deg_s=vt.tolist()),controller_completion_margins=cfg['controller_completion_margin'],reference_proxy_limit='Position and near-zero reference velocity are only a diagnostic proxy. Actual transition also needs original reference ownership/continuation-to-zero-acceleration and controller-tightened readiness. No proxy replaces the unchanged state machine/evaluator.',rows=rows)
    text=json.dumps(output,indent=2)+'\n'
    lines=['# Why positional progress is not task acquisition','', 'Offline read-only diagnostics. Existing task requires both joints within1 degree and below2 degrees/s, with original tighter controller margins and reference ownership/readiness. The numerical proxy does not replace these semantics.','', '|Arm|Step|Scope|Tag|Position progress|Goal-box samples|Position+velocity samples|HOLD|Final q (deg)|','|---|---:|---|---|---:|---:|---:|---|---|']
    for x in rows.values():lines.append(f'|{x["arm"]}|{x["training_step"]}|{x["scope"]}|{x["tag"]}|{x["max_synchronized_position_progress"]:.5f}|{x["position_box_samples"]}|{x["position_and_velocity_samples"]}|{x["entered_HOLD"]}|{x["final_q_deg"]}|')
    for folder in (D,L):
        (folder/'OUTBOUND_SETTLING_AUDIT.json').write_text(text)
        (folder/'OUTBOUND_SETTLING_AUDIT.md').write_text('\n'.join(lines)+'\n')
    shutil.copy2(Path(__file__),S/'scripts/demo_assisted_sac_task_acquisition_v1'/Path(__file__).name)
    print(json.dumps({k:v for k,v in rows.items() if v['training_step']==50000 and v['scope']=='NATIVE' and v['tag']=='final'},indent=2))
if __name__=='__main__':run()
