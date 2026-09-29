# Scientific Simulation Mode status

**SCIENTIFIC_SIMULATION_MODE_VALIDATED on Mac under the mode-aware evaluation contract v1.** The frozen V2 evaluation retains scorer-v2's original raw output and assesses its physical/task/safety conditions separately from realtime host age. Four new 0/100/200/500 ms runs completed, passed common physical and scientific validity, and matched exactly over 48 trace arrays and 104,180 native states. Four preregistered representative scientific runs also completed and passed. See `MODE_AWARE_EVALUATION_CONTRACT.md`, `HOST_DELAY_COMPARISON_V2.json`, `REPRESENTATIVE_SCIENTIFIC_RESULTS.json`, and `MODE_AWARE_IMPLEMENTATION_REPORT.md`.

Valid for deterministic simulation-time algorithmic research, Human model adaptation, waypoint studies, future value/RL comparison, and modeled task/safety evaluation under the recorded case family. This validation is bounded development evidence, not an independent robustness campaign.

Not valid for realtime qualification, a CR12 timing guarantee, safe hardware timeout, unattended rehabilitation, or clinical safety. Real host plan age is still logged: the V2 500 ms run reached 583.76625 ms. Original scorer-v2 remains FAIL on `plan_age` for the delayed scientific runs, and realtime mode still rejects >=100 ms stale results.

Historical `RSS_RUNTIME_QUALIFICATION_NOT_MET` remains. `RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS` remains a hard milestone.

## Retained V1 failure

The prior **SCIENTIFIC_SIMULATION_VALIDATION_FAIL** result is not relabeled. Its original contract required all raw scorer-v2 conditions PASS; 100/200/500 ms failed raw `plan_age`. `IMPLEMENTATION_REPORT.md`, `HOST_DELAY_COMPARISON.json`, and the V1 raw data preserve that outcome. V2 is a separately frozen mode-aware evaluation contract with fresh runs.

The experimental adapter freezes simulation physics during worker computation and command construction; a committed 5 ms command advances 20 native steps. Real host compute and activation ages remain in the logs. This is an ideal simulation-time execution assumption.
