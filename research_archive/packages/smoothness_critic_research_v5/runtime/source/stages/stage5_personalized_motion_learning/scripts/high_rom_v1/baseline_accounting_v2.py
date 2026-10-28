"""Measured-wrench task accounting on the frozen 5 ms execution grid."""
from __future__ import annotations

import numpy as np


CONTROL_INTERVAL_S = 0.005
MAX_RECORDED_INTERVAL_ERROR_S = 1e-9


def task_wrench_cost(trace, mask) -> dict:
    time = np.asarray(trace['time_s'][mask], dtype=float)
    force = np.asarray(trace['physical_cuff_force_world_n'][mask], dtype=float)
    moment = np.asarray(trace['physical_cuff_moment_world_nm'][mask], dtype=float)
    saved_interval_cost = np.asarray(trace['interval_force_cost_n_s'][mask], dtype=float)
    if (time.ndim != 1 or len(time) < 2 or force.shape != (len(time), 3)
            or moment.shape != (len(time), 3) or saved_interval_cost.shape != (len(time),)
            or not all(np.all(np.isfinite(x)) for x in (time, force, moment, saved_interval_cost))):
        raise ValueError('invalid measured-wrench trace')
    observed_dt = np.diff(time)
    if (np.any(observed_dt <= 0)
            or np.any(np.abs(observed_dt - CONTROL_INTERVAL_S) > MAX_RECORDED_INTERVAL_ERROR_S)):
        raise ValueError('task trace does not follow the frozen 5 ms execution grid')
    force_norm = np.linalg.norm(force, axis=1)
    moment_norm = np.linalg.norm(moment, axis=1)
    force_cost = float(np.sum(force_norm[:-1] * CONTROL_INTERVAL_S))
    interval_sum = float(np.sum(saved_interval_cost))
    if not np.isclose(force_cost, interval_sum, rtol=0, atol=1e-8):
        raise ValueError('measured force disagrees with saved interval force costs')
    return {
        'J_F_n_s': force_cost,
        'moment_integral_nm_s': float(np.sum(moment_norm[:-1] * CONTROL_INTERVAL_S)),
        'peak_force_n': float(force_norm.max()),
        'peak_moment_nm': float(moment_norm.max()),
        'sample_count': len(time),
        'interval_count': len(observed_dt),
        'max_recorded_interval_error_s': float(np.max(np.abs(observed_dt-CONTROL_INTERVAL_S))),
        'clock_basis': 'frozen_5ms_execution_interval_verified_against_recorded_time',
    }
