"""Single offline interface specimen. No plant is constructed or commanded."""
import hashlib
import json
import math
import os
import platform
import sys
import time
import traceback
from dataclasses import replace
from decimal import Decimal as D, localcontext
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
RT2 = HERE.parent / "ihear_lab_stage1_rt2_v1"
sys.path.insert(0, str(RT2))
import env_rt2
from fixtures import native_context
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation, clearance_geometry_signature
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
from traction_mpc_stage5.human_waypoint_scheduler import ScheduledHumanReferenceSample
from traction_mpc_stage5.task import TaskPhase

def no_step(*args, **kwargs):
    raise AssertionError("Physics is outside this probe")

for name in ("mj_step", "mj_step1", "mj_step2"):
    setattr(mujoco, name, no_step)

def load(path):
    return json.loads(path.read_text())

def directions(G, remaining, V, A, Fp, h):
    # OUTBOUND, two mobile axes and zero committed speed in this specimen.
    def unit(b):
        return (G @ b) / np.linalg.norm(G @ b)
    current = unit(remaining)
    def turn(b):
        d = unit(b)
        return math.atan2(current[0]*d[1]-current[1]*d[0], current @ d)
    top = np.minimum(V, A*h)
    corners = [top*np.array(mask) for mask in [(0,1), (1,0), (1,1)]]
    bounds = [("current",remaining), ("left", max(corners,key=turn)), ("right",min(corners,key=turn))]
    rows = []
    for label,b in bounds:
        ray = b / np.linalg.norm(G @ b)
        d = unit(b)
        score = abs(Fp @ d)
        rows.append(dict(label=label, direction=d, c=ray, angle_rad=turn(b), score_N=score))
    index = min(range(len(rows)), key=lambda i:(rows[i]["score_N"], i!=0, abs(rows[i]["angle_rad"]), i))
    row = rows[index]
    caps = np.minimum(V, remaining/h)
    positive = row["c"] > 0
    speed_cap = min(caps[positive] / row["c"][positive])
    speed = speed_cap * math.exp(-row["score_N"]/200)
    return rows, index, speed_cap, speed, speed*row["c"]

class RestSegment:
    """Analytic solution only for the predeclared first hold of r from rest."""
    duration_s = .040
    continuous_clearance_certificate = None

    def __init__(self, q, r, omega):
        self.start_q_rad = q.copy()
        self.start_dq_rad_s = np.zeros(2)
        self.r = r.copy()
        self.omega = omega

    def sample(self,elapsed):
        assert 0 <= elapsed <= self.duration_s
        with localcontext() as ctx:
            ctx.prec = 65
            t, w = D.from_float(float(elapsed)), D.from_float(self.omega)
            x = w*t
            decay = (-x).exp()
            v = 1 - (1+x)*decay
            z = 1 - decay
            s = t - (v+z)/w
            a = w*x*decay
        return ScheduledHumanReferenceSample(self.start_q_rad+self.r*float(s), self.r*float(v), self.r*float(a))

def main():
    raw = load(RT2/"B/native/runtime_artifacts.json")
    summary = load(RT2/"B/native/summary.json")
    b, spec, scheduler, _ = native_context()
    handoff = summary["commissioning"]["handoff_belief"]
    older = (Path(__file__).resolve().parents[4] / 'adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3/key_traces/historical_B/summary.json')
    assert handoff == load(older)["commissioning"]["handoff_belief"]
    row = next(row for row in raw["trace"] if row["stage"]=="TASK")
    stamp = row["time_s"]
    causal = next(item for item in raw["wall_physics"]["causal_sensor_estimates"] if item["sample_time_s"]==stamp)
    xhat = np.asarray(causal["estimated_state"])
    assert np.array_equal(xhat,row["estimated_state"])
    F = np.asarray(row["cuff_force_world_n"])
    q = np.asarray(row["q_ref_rad"])
    goal = np.asarray(spec.outbound_goal_target_rad)
    phase = TaskPhase.OUTBOUND
    clearance = scheduler.clearance_evaluator
    def admission(schedule, origin):
        return validate_activation(belief=b,request_sequence=b.sequence,schedule=schedule,
            clearance=clearance,phase=phase,request_phase=phase,remaining_s=spec.phase_timeout_s,
            reference_state=origin,now_physics_s=stamp,certificate_geometry_at_request=clearance_geometry_signature(clearance))
    # Only the B positive control is a quintic. Rebuild the archived chosen path.
    dec = raw["task_decisions"][0]
    rec = next(e["schedule"] for e in dec["evaluations"] if e["label"]==dec["executed_label"])
    # Use RT2's original replay for the B control only; its samples do not feed the new reference.
    import software_aligned as replay
    replay.BASE = RT2/"B/native"
    reference_rows = replay.reconstruct()
    try:
        i,k,base,_,_,_,_ = next(reference_rows)
    finally:
        reference_rows.close()
    assert (i,k)==(0,0)
    assert base.record() == rec
    control = admission(base,np.r_[base.start_q_rad,base.start_dq_rad_s])
    assert control["feasible"]

    V = scheduler.reference_velocity_fraction*np.asarray(spec.task_joint_velocity_limit_rad_s)
    A = scheduler.reference_acceleration_fraction*np.asarray(spec.task_joint_acceleration_limit_rad_s2)
    with localcontext() as ctx:
        ctx.prec=65
        upper = D(1).exp()*min(D.from_float(float(a))/D.from_float(float(v)) for a,v in zip(A,V))
        omega = math.nextafter(float(upper),0.)
        assert D.from_float(omega) < upper
    geom = b.human_model().geometry
    E = np.column_stack((geom.plane_x_world,geom.plane_z_world))
    G = E.T @ geom.translational_jacobian_world(xhat[:2])
    h = RestSegment.duration_s
    assert np.linalg.matrix_rank(G)==2 and np.all(goal>q)
    rows,index,cap,speed,r = directions(G,goal-q,V,A,E.T@F,h)
    assert np.any(r>0) and np.all(r<=np.minimum(V,(goal-q)/h))
    seg = RestSegment(q,r,omega)
    end = seg.sample(h)
    seg.candidate = runtime._candidate("fgdw_rest_probe",phase,end.q_rad,end.dq_rad_s,spec)
    seg.version = "FGDW-v1/rest-interface-fixture"
    mechanics = AdaptiveMechanicsScreenV22().evaluate(b,seg.candidate,seg)
    start = time.perf_counter_ns()
    try:
        admission_record = admission(seg,np.r_[q,[0.,0.]])
        result = dict(returned=True, feasible=admission_record["feasible"])
    except AttributeError as exc:
        result = dict(returned=False,exception_type=type(exc).__name__,message=str(exc),
                      stack=traceback.format_exc())
        if exc.name!="coefficients" or exc.obj is not seg: raise
    result["diagnostic_admission_elapsed_ns"] = time.perf_counter_ns()-start
    return dict(utc_ns=time.time_ns(),source_time_s=stamp,phase=phase.value,belief=b.sequence,
        original_q=q,original_dq=row["dq_ref_rad_s"],original_ddq=row["ddq_ref_rad_s2"],
        xhat=xhat,F=F,E=E,G=G,F_plane=E.T@F,raw_directions=rows,selected=index,v_cap=cap,
        desired=speed,r=r,limits_v=V,limits_a=A,omega=omega,goal=goal,end_q=end.q_rad,
        end_dq=end.dq_rad_s,end_ddq=end.ddq_rad_s2,delta=end.q_rad-q,
        fast_candidate_fields=list(vars(seg.candidate)),base_positive=control,
        base_matches_archive=True,mechanics=mechanics,native_admission=result,
        native_write_attempts=0,applied=0,steps=0,platform=platform.platform(),affinity=sorted(os.sched_getaffinity(0)),
        python=sys.version,numpy=np.__version__,mujoco=mujoco.__version__,
        thread_config={k:os.environ[k] for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")})

if __name__=="__main__":
    result=main()
    with (HERE/"probe_result.json").open("x") as stream:
        json.dump(result,stream,indent=2,allow_nan=False,default=lambda v:v.tolist() if isinstance(v,np.ndarray) else v.item())
    print(json.dumps(result["native_admission"]))
