# Experiment logging and retention

Assign a stable `study_id` to the scientific question and a unique `run_id` to
each attempt. A retry gets a new run ID and refers back to its parent. Freeze
the hypothesis, method, code revision, configuration identity, Human condition,
seed, clock, comparison arms, budget, metrics, units and qualification rules
before collecting evidence.

Keep one compact row per planned slot. Record whether it started, completed,
qualified, failed, was rejected, or remained unrun. Preserve the reason, scope of
the measurement and the denominator used by each statistic. Keep the full
denominator alongside the qualified subset. Record phase-specific trends,
extrema and integrals where relevant, the conclusion, stop reason and the
research question that could justify returning to this work.

| Class | Retention |
| --- | --- |
| S0 | Active dependencies and frozen inputs, with identity and required path. |
| S1 | Raw evidence, comparison arms, key counterexamples and scoring entry points necessary for a formal claim. |
| S2 | Full formal result table, conditions, qualifications and representative evidence for a closed study. |
| A | Historical methods, trends, negative results and lessons. |
| B | Exploration output eligible for retirement after verified extraction and an authorized disposition. |

Dense data may be written during a run. At closeout, decide which samples must
remain to support each claim. Identify a canonical copy by digest. Record the
evidence grade, sample rate, any downsampling, retained comparisons, recovery
source and analyses lost after retirement. Keep failed and unrun rows visible.
Use an immutable code revision and environment specification in place of copying
the full source tree or environment into each experiment.

Use `runs/` or a study-specific `scratch/` for temporary output, a compact table
for results, and an access-controlled archive for internal evidence. Place
credentials and private configurations outside the publication set. Check active
dependencies, publication and collaboration obligations, repository status and
authorization before retiring files. The threshold, safety, freeze and approval
rules in the root AGENTS.md continue to apply.
