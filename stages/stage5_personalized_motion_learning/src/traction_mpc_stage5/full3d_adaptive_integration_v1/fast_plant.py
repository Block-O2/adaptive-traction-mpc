"""Versioned equation-equivalent interface cache and observation-free stepping.

The historical Stage-3/Stage-5 plant source is not modified. Cache keys contain
every input to evaluate_interface, not time or q alone. Cached arrays are never
returned to callers: frozen dataclasses do not make their arrays immutable.
"""
import mujoco
import numpy as np

from .fast_interface import ExactInterfaceEvaluator, parameter_key
from ..cr12_plant import Stage5CR12SensorBoundaryPlant


class CachedStage5CR12SensorBoundaryPlant(Stage5CR12SensorBoundaryPlant):
    def __init__(self, *args, **kwargs):
        self._interface_evaluator = ExactInterfaceEvaluator()
        self._interface_key = None
        self._interface_value = None
        self.interface_cache_hits = 0
        self.interface_cache_misses = 0
        super().__init__(*args, **kwargs)

    def _evaluate_current_interface_value(self):
        robot = self._attachment_state(self.attachment_site_id)
        human = self._attachment_state(self.sleeve_site_id)
        parameters = self.interface_parameters
        key = (parameter_key(parameters),
               tuple(value.tobytes() for state in (robot,human)
                     for value in (state.position_world_m,state.rotation_world,
                                   state.velocity_world_m_s,state.angular_velocity_world_rad_s)))
        if key != self._interface_key:
            self._interface_value = self._interface_evaluator.evaluate(parameters, robot, human)
            self._interface_key = key
            self.interface_cache_misses += 1
        else:
            self.interface_cache_hits += 1
        return self._interface_value

    def _evaluate_current_interface(self):
        value = self._evaluate_current_interface_value()
        return type(value)(*(x.copy() if isinstance(x, np.ndarray) else x for x in vars(value).values()))

    def _apply_interface(self):
        # Private read always validates the complete current input key; unlike
        # post-refresh history reuse this must not read an old cached value.
        state = self._evaluate_current_interface_value()
        self.interface_generalized_force[:] = 0.
        for site_id,wrench in ((self.sleeve_site_id,state.human_wrench_world),
                               (self.attachment_site_id,state.robot_wrench_world)):
            mujoco.mj_applyFT(self.model,self.data,wrench[:3],wrench[3:],
                self.data.site_xpos[site_id],int(self.model.site_bodyid[site_id]),self.interface_generalized_force)
        self.data.qfrc_applied[:] += self.interface_generalized_force

    def step_native(self):
        """Same original step/refresh order; omit unused full observations."""
        self.data.eq_active[self.weld_id] = 0
        mujoco.mj_step1(self.model, self.data)
        self._apply_soft_limit()
        self._apply_interface()
        mujoco.mj_step2(self.model, self.data)
        self._refresh()
        # _refresh just evaluated the post-integration interface to apply its
        # forces. mj_forward does not change qpos/qvel, hence neither site
        # pose nor twist. Reuse that private value only for copied history;
        # external callers still receive defensive copies and full-key checks.
        state = self._interface_value
        record = {"time_s": float(self.data.time),
                  "translation_m": state.displacement_human_m.copy(),
                  "rotation_rad": state.rotation_error_human_rad.copy()}
        if self.interface_history and abs(self.interface_history[-1]["time_s"]-self.data.time) < 1e-12:
            self.interface_history[-1] = record
        else:
            self.interface_history.append(record)
