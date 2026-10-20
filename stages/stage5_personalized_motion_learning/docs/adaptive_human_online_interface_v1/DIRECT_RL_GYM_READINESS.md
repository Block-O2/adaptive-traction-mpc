# Direct-RL Gym readiness

SMOKE_PASS: two sequential seed-20261002 non-scientific API smoke episodes at 20 ms. Each has one physics owner thread; no vector workers, policy optimization or replay training.

| episode | reset | invalid action rejected | steps | terminated | truncated | post-terminal reject | physical |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deterministic | True | True | 594 | True | False | True | PASS |
| random_safe | True | True | 594 | True | False | True | PASS |


Action Box[-1,1]² maps to ±0.05 rad target increments relative to the current phase soft target. Explicit ROM clipping is returned in info; current full-path safety acceptance remains mandatory. No Human torque action exists. Observation has 47 finite causal entries: estimated q/dq, owned q/dq/ddq, estimated beta/residual, measured wrench, estimated effective geometry, phase, task time and nominal soft target. Private physical truth is used only to construct the hidden plant; it is never placed in the observation. The existing ideal simulated measurement/derivative assumption remains.

COMPLETE is observed as terminated=True/truncated=False. API-only injected terminal records additionally test timeout → truncated, safety abort → terminated, and COMPLETE → terminated; these mapping checks are not additional physical timeout tests. Nonfinite/out-of-space action validation comes from Gym Box checks; actual smoke explicitly tests out-of-range rejection before physics advances and rejects step after terminal. Repeated reset support is implemented but multi-episode reset longevity is not qualified by this two-instance smoke.

Zero reward is intentional API scaffolding. Serious single-Human SAC campaign is NOT yet qualified: scientific reward, normalization, throughput, episode/reset stress behavior, evaluation seeds and frozen SAC experiment contract need completion. No RL algorithm comparison was performed.
