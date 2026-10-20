# SAC R2 scientific analysis

1. What caused 1.020s HOLD?

Two .5s stationary certified schedules, each with one 5ms asynchronous activation wait and one 5ms receipt-owned endpoint recognition. Phase transitions are checked every 5ms, before reference progress commit. No controller bug or SAC-period quantization.

2. What timing protocol is frozen and why?

Physical .5s contiguous valid HOLD unchanged; MATCHED minima 9/1/9s, each upper bound +max(.020 policy tick, 2*(.005 activation+.005 receipt recognition))+.000000001s. Same range for every method, source-derived before SAC training.

3. Do original controller and strong comparators qualify fairly?

PASS

4. Is fixed hip-leading ~877.7 primarily timing, coordination, or unresolved?

Native reduction includes substantial duration effects. After common timing eligibility, a smaller matched benefit remains. Coordination versus within-phase pacing is unresolved as a causal decomposition.

5. Did SAC train successfully?

Formal CUDA optimization executed with finite logged losses; the resource stop prevented the meaningful >=300k campaign. No valid learned expert is confirmed.

6. Best SAC NATIVE J_F?

None

7. Best SAC MATCHED J_F?

None

8. Does SAC beat original, fixed, CEM?

No confirmed valid SAC candidate, so no beating claim.

9. Does SAC discover different coordination?

No confirmed valid SAC trajectory exists for this claim.

10. Does integral reduction increase peaks?

No SAC result. Fixed comparator reduces cost while its force/moment peaks exceed old nominal.

11. Is learning still improving at stop?

None

12. Is more SAC justified before TQC/PPO?

Review measured warmup/reset throughput and valid independent checkpoint trend on this unchanged contract first. Do not switch algorithms to bypass an unresolved resource, throughput or valid-task limitation.

Detailed phase metrics, raw traces, lead/lag statistics and comparisons are in JSON. Native and MATCHED-TIMING are separate rankings; timing allowance does not equalize within-phase pacing.
