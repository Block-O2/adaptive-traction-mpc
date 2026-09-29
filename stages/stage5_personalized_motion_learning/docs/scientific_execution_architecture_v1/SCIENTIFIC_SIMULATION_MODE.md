# Scientific Simulation Mode status

**SCIENTIFIC_SIMULATION_VALIDATION_FAIL.** The Mac implementation attempt produced exact host-delay-invariant native and trace trajectories in one 120°/120° nominal case. Its unchanged scorer-v2 failed `plan_age` at 100/200/500 ms host-only delay. The preregistered acceptance required all scorer-v2 conditions to pass, so this mode is not promoted for algorithmic comparison, adaptation research, waypoint selection or value-learning experiments.

The experimental adapter freezes simulation physics during worker computation and command construction; a committed 5 ms command advances 20 native steps. Real host compute and activation ages remain in the logs. This is an ideal simulation-time execution assumption, not evidence of hard realtime, hardware timing, safe command timeout, CR12 control readiness or clinical safety.

Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` remains FAIL. `RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` remains a hard milestone. See `IMPLEMENTATION_REPORT.md` and `HOST_DELAY_COMPARISON.json` for the retained negative result.
