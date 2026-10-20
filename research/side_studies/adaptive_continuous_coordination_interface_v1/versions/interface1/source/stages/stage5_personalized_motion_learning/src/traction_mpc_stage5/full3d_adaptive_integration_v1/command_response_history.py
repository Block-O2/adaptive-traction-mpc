"""Receipt-owned commanded-wrench average for a causal acceleration window.

This aligns internal model inputs, not actual transmitted force or robot delay.
"""
from __future__ import annotations
import numpy as np


class CommandResponseHistory:
    def __init__(self):
        self.rows = []

    def record(self, time_s, source_sample_s, force, moment, robot_point, *, receipt_index):
        values = [np.asarray(v, dtype=float) for v in (force, moment, robot_point)]
        if (not np.isfinite(time_s) or not np.isfinite(source_sample_s)
                or source_sample_s > time_s + 1e-10
                or any(v.shape != (3,) or not np.all(np.isfinite(v)) for v in values)):
            raise ValueError('finite causal command receipt required')
        if self.rows and time_s < self.rows[-1]['time_s']:
            raise ValueError('command receipt order reversed')
        if (isinstance(receipt_index, bool) or not isinstance(receipt_index, int) or receipt_index < 0
                or (self.rows and receipt_index <= self.rows[-1]['receipt_index'])):
            raise ValueError('strictly increasing actual receipt identity required')
        self.rows.append(dict(receipt_index=receipt_index, time_s=float(time_s), source_sample_s=float(source_sample_s),
                              force=values[0].copy(), moment=values[1].copy(), point=values[2].copy()))
        # Retain the owner crossing the cutoff, including across long holds.
        while len(self.rows) > 1 and self.rows[1]['time_s'] <= time_s - 1.0:
            self.rows.pop(0)

    def average(self, start_s, end_s, human_point):
        point = np.asarray(human_point, dtype=float)
        if (not np.isfinite(start_s) or not np.isfinite(end_s) or end_s <= start_s
                or point.shape != (3,) or not np.all(np.isfinite(point))):
            raise ValueError('finite positive causal response window required')
        if not self.rows or self.rows[0]['time_s'] > start_s + 1e-10:
            raise RuntimeError('COMMAND_RESPONSE_WINDOW_NOT_COVERED')
        first = len(self.rows) - 1
        while first > 0 and self.rows[first]['time_s'] > start_s:
            first -= 1
        force, moment = np.zeros(3), np.zeros(3)
        contributions = []
        covered = 0.0
        for index in range(first, len(self.rows)):
            row = self.rows[index]
            left = max(start_s, row['time_s'])
            right = min(end_s, self.rows[index + 1]['time_s'] if index + 1 < len(self.rows) else end_s)
            if right > left:
                duration = right - left
                weight = duration / (end_s - start_s)
                rebased = row['moment'] + np.cross(row['point'] - point, row['force'])
                force += weight * row['force']
                moment += weight * rebased
                covered += duration
                contributions.append({**row, 'interval_start_s': left, 'interval_end_s': right,
                                      'weight': weight, 'moment_about_current_human_point_nm': rebased})
            if right >= end_s:
                break
        if abs(covered - (end_s - start_s)) > 1e-10:
            raise RuntimeError('COMMAND_RESPONSE_WINDOW_NOT_COVERED')
        return force, moment, {'start_s': float(start_s), 'end_s': float(end_s),
            'current_causal_human_point_m': point.copy(), 'contributions': contributions,
            'averaged_command_force_n': force.copy(), 'averaged_command_moment_nm': moment.copy(),
            'scope': 'receipt-duration-weighted commanded wrench; not measured transmitted force or a future response bound'}
