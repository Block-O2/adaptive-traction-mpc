# Hardware translation boundary

SCIENTIFIC_SIMULATION isolates scientific methodology from host scheduling; it cannot replace runtime assurance. Before real CR12 experiments the project still requires realtime executor, independent watchdog/heartbeat, bounded command timeout, trajectory buffering, safe braking/hold including commissioning, force/velocity/joint limits, real-time OS/controller integration, timing fault tests, WCET/latency characterization and E-stop. These are REQUIRED_BEFORE_HARDWARE_EXPERIMENTS.

Historical RSS_RUNTIME_QUALIFICATION_NOT_MET remains FAIL. Earlier 55 ms activation failures, the failed fresh49 commissioning command, incomplete/negative results and scientific-simulation runner-only scope decision are unchanged. Safe Fallback covers part of TASK and is not a hardware safety proof.

Existing WSL closeout: CROSS_HOST_RESULT_INCONCLUSIVE, 24 slots = 6 COMPLETE / 15 ABORTED / 3 EXCEPTION; 102/243 activation events >55 ms, max96.652 ms; maximum command gap375.038 ms; 19 fallback commits. Its lack of the earlier ~191 ms planner tail is not evidence that system-level timing instability was solved. Mac reference was not exact-HEAD/repetition matched. Scorer-v2 provenance confirms post-run/offline equality for a saved native trajectory, not general runtime qualification.

Keep every result mode-tagged, host-profiled and source-versioned. A scientific success is neither a replacement for a realtime failure nor evidence for hard realtime, clinical safety or patient suitability. No hardware was actuated in this audit.
