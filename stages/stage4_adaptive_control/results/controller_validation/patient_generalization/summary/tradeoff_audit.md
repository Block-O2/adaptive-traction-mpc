# Trade-off audit

Only cases with lower tracking RMSE on the right-hand controller and at least one worsened preregistered category are listed.

- Nominal, seed 44104, PD+FF -> Fixed MPC: RMSE change -0.0912°, worsened cuff_force_or_moment, robot_joint_torque.
- Nominal, seed 54113, Fixed MPC -> Adaptive MPC: RMSE change -0.0005°, worsened cuff_force_or_moment, robot_joint_torque.
- Nominal, seed 64122, Fixed MPC -> Adaptive MPC: RMSE change -0.0033°, worsened cuff_force_or_moment, robot_joint_torque.
- +5% mass, seed 44104, PD+FF -> Fixed MPC: RMSE change -0.0522°, worsened cuff_force_or_moment, robot_joint_torque.
- +5% mass, seed 44104, Fixed MPC -> Adaptive MPC: RMSE change -0.0568°, worsened cuff_force_or_moment, robot_joint_torque.
- +5% mass, seed 54113, Fixed MPC -> Adaptive MPC: RMSE change -0.0292°, worsened acceleration, jerk, cuff_force_or_moment, robot_joint_torque.
- +5% mass, seed 64122, Fixed MPC -> Adaptive MPC: RMSE change -0.0187°, worsened acceleration, jerk, cuff_force_or_moment, robot_joint_torque.
- +3% geometry, seed 44104, PD+FF -> Fixed MPC: RMSE change -0.1348°, worsened cuff_force_or_moment, robot_joint_torque.
- +3% geometry, seed 44104, Fixed MPC -> Adaptive MPC: RMSE change -0.0276°, worsened cuff_force_or_moment, robot_joint_torque.
- +3% geometry, seed 54113, PD+FF -> Fixed MPC: RMSE change -0.0373°, worsened max_tracking_error, cuff_force_or_moment, robot_joint_torque.
- +3% geometry, seed 54113, Fixed MPC -> Adaptive MPC: RMSE change -0.0134°, worsened cuff_force_or_moment, robot_joint_torque.
- +3% geometry, seed 64122, Fixed MPC -> Adaptive MPC: RMSE change -0.0156°, worsened cuff_force_or_moment, robot_joint_torque.
- Moderate mixed, seed 44104, Fixed MPC -> Adaptive MPC: RMSE change -0.1047°, worsened cuff_force_or_moment, robot_joint_torque.
- Moderate mixed, seed 54113, Fixed MPC -> Adaptive MPC: RMSE change -0.1442°, worsened acceleration, jerk, cuff_force_or_moment, robot_joint_torque.
- Moderate mixed, seed 64122, Fixed MPC -> Adaptive MPC: RMSE change -0.1645°, worsened cuff_force_or_moment, robot_joint_torque.

Acceleration and jerk are offline motion-smoothness descriptors, not comfort or clinical-safety truth. Cuff quantities are engineering interaction loads, not pressure or tissue safety.
