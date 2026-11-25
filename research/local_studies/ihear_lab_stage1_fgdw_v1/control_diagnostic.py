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
    base_candidate = runtime._candidate(dec["executed_label"],phase,np.array(rec["target_q_rad"]),np.array(rec["target_dq_rad_s"]),spec)
    base = scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=np.array(rec["start_q_rad"]),
        current_dq_hat_rad_s=np.array(rec["start_dq_rad_s"]),candidate=base_candidate,duration_s=rec["duration_s"])

    saved=base.record()
    for k in sorted(set(saved)|set(rec)):
        if saved.get(k)!=rec.get(k):
            print(k,repr(saved.get(k))[:900],repr(rec.get(k))[:900])
main()
