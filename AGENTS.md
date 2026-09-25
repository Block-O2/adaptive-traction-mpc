# AGENTS.md

## Project Scope

This repository is for adaptive traction MPC experiments.

The long-term research goal is to develop and compare fixed MPC, online
identification, adaptive MPC, and later robust/safe/learning-assisted adaptive
control in a controlled, reproducible, scientifically defensible way.

The repository contains historical Stage 1–5 work. Historical evidence,
negative results, and previously frozen scientific artifacts are part of the
research record and must not be silently rewritten.

---

## Core Execution Discipline

Codex must execute only the task described in the user's current prompt.

Do not make extra scientific, algorithmic, physical, or parameter changes unless
the current user prompt explicitly authorizes them.

In particular, unless explicitly authorized, do not independently:

- tune controller parameters because results look bad;
- change cost weights;
- change constraints;
- change physical parameters;
- change noise or bias settings;
- change target angle;
- change optimizer settings;
- change solver settings;
- change max_time, max_steps, or effective rollout duration;
- add gravity compensation;
- add hidden clipping or hidden safety logic;
- replace the algorithm;
- add new experiments;
- remove failed results;
- hide or overwrite unfavorable outputs;
- reduce the scientific unknown set;
- reinterpret simulation truth as deployable information;
- weaken acceptance criteria after seeing results.

Bad results are valid experimental results.

Treat exploratory runs as exploratory only. Do not silently fold exploratory
tuning back into formal configs or scientific claims.

If a run fails, gets stuck, violates constraints, or produces poor performance,
preserve and report the evidence.

---

# Explicit Research Authorization Modes

The repository is conservative by default.

However, the current user prompt may explicitly grant additional scientific
authority.

The following phrases have special meaning when they appear explicitly in the
current user task:

## `FORMAL EXPERIMENTS AUTHORIZED`

When the current user prompt explicitly states:

    FORMAL EXPERIMENTS AUTHORIZED

Codex is authorized to autonomously run simulation/offline computational formal
scientific experiments reasonably necessary to complete that task.

This includes, where relevant:

- MuJoCo simulation campaigns;
- preregistered formal experiments;
- randomized hidden-condition studies;
- Monte Carlo studies;
- parameter/sensitivity sweeps;
- identifiability and observability studies;
- ablations;
- oracle-vs-estimated comparisons;
- held-out validation;
- formal regression campaigns;
- reproduction of historical experiments when required for verification;
- long-running engineering or scientific simulation jobs.

This authority applies only to simulation/offline computational work.

It does NOT authorize:

- physical CR12 actuation;
- any other real robot or physical-device actuation;
- human or animal experiments;
- destructive physical-device actions;
- paid external compute jobs that create additional charges;
- credential/account changes;
- uploading private repository data to third-party services.

Real-hardware experiments require separate explicit user authorization.

---

## `AUTONOMOUS RESEARCH CAMPAIGN AUTHORIZED`

When the current user prompt explicitly states or clearly establishes an
autonomous research campaign, Codex may continue through multiple predefined
research phases without waiting for routine user confirmation, provided that:

1. the scientific objective is fixed;
2. the Master Contract / approved experiment contract is fixed;
3. hard phase gates are defined in advance;
4. stop conditions are defined in advance;
5. scientific-integrity requirements below are obeyed.

Within such an authorized campaign, Codex may autonomously decide HOW to solve
the approved problem, including:

- estimator choice;
- structured identification method;
- filtering method;
- numerical implementation;
- refactoring;
- diagnostic instrumentation;
- focused development experiments;
- preregistered formal experiments;
- bounded scientific comparisons;
- repair of implementation defects;
- literature-supported methodological changes;

provided those decisions do not change WHAT scientific problem is being asked.

Codex may NOT autonomously:

- reduce the required unknown set;
- redefine the research objective;
- relax formal thresholds after seeing held-out results;
- shrink the hidden setup family merely to make results pass;
- introduce oracle inputs into deployable code;
- add a new sensor assumption to the intended deployment system;
- replace a required online estimate with fixed nominal truth;
- convert a failed scientific result into a passing result by changing the
  contract post hoc.

If continuing requires one of those changes, stop and report that human approval
is required.

---

## Multi-Agent Authority

Use a single agent by default.

Multiple agents/subagents are allowed when:

- the user explicitly requests them; or
- the current autonomous research campaign explicitly defines independent
  implementation and audit roles.

For scientific recovery/audit tasks, a recommended structure is:

- Builder / Orchestrator:
  implementation, tests, experiments, repairs;
- Independent Auditor:
  adversarial review of assumptions, truth leakage, scientific validity,
  held-out discipline, and claims.

Where possible, Auditor should have independent context and should not inherit
all Builder reasoning.

Multiple agents editing the same production files concurrently should be
avoided.

The purpose of multiple agents is scientific independence and error detection,
not merely increased token usage.

---

# Scientific Integrity Requirements

These requirements apply to all formal scientific experiments.

Before a formal held-out experiment or formal scientific campaign begins,
freeze and record:

- hypothesis or scientific question;
- experimental setup family;
- development vs held-out split;
- allowed controller/estimator inputs;
- hidden/oracle quantities;
- metrics;
- pass/fail or promotion criteria;
- seeds or seed-generation rule;
- experiment budget;
- exclusion criteria;
- relevant scientific variables;
- simulation-truth firewall.

Do not weaken or redefine acceptance criteria after seeing held-out results.

If a scientific contract must change after observing results:

1. preserve the original result;
2. mark it accurately as failed/inconclusive/blocked as appropriate;
3. version the revised study separately;
4. return to development;
5. preregister the revised experiment before rerunning;
6. use fresh held-out cases when the old held-out set has already influenced
   design decisions.

Do not repeatedly tune against the same held-out set until it passes.

Preserve negative results and failed runs.

Never silently discard failed cases.

Every formal experiment must preserve enough provenance to reproduce it:

- exact config;
- exact command;
- branch and code revision;
- environment;
- seeds;
- output paths;
- relevant logs;
- summary metrics;
- failed-attempt records;
- whether source/config/scientific setup changed.

---

# Simulation-Truth Firewall

Simulation truth may be used for:

- hidden-condition generation;
- oracle baselines;
- evaluation;
- held-out error calculation;
- post-run diagnosis.

Unless the current scientific contract explicitly says otherwise, simulation
truth may NOT enter:

- deployable estimator inputs;
- controller state;
- Jacobian construction for the deployable path;
- generalized-force mappings used by the deployable controller;
- candidate generation;
- MPC prediction;
- online dynamic-identification inputs;
- model-promotion decisions;
- action selection.

Oracle configurations must be clearly separated from deployable configurations.

Where practical, add tests or source/data-flow guards that fail loudly if
deployable code accesses hidden truth.

If a required quantity is not identifiable from the allowed deployment
observations, report the identifiability failure.

Do not hide an identifiability failure by:

- injecting oracle information;
- silently fixing the parameter to nominal truth;
- reducing the unknown set;
- allowing unrelated dynamic parameters to absorb geometry error and then
  claiming geometry was identified.

A scientifically justified `BLOCKED_IDENTIFIABILITY` outcome is preferable to a
false successful result.

---

# Research Assumptions and Scope Drift

Experimental freezing is not automatically a permanent system assumption.

If a quantity was frozen for a historical capability, debugging, or ablation
study, do not assume it is permanently known in the intended architecture.

For architecture-recovery tasks, explicitly distinguish:

- STRUCTURAL_PRIOR
- MEASURED
- CALIBRATED
- ONLINE_ESTIMATED
- FIXED_NOMINAL
- SIMULATION_TRUTH
- HIDDEN_ORACLE

Every control-critical quantity should have a traceable source.

If repository history and the current implementation disagree about the intended
status of a quantity, document the evidence rather than silently choosing the
convenient interpretation.

---

# Required Behavior When Results Look Bad

## Default non-autonomous tasks

If results are poor but scripts complete:

- save outputs;
- summarize what happened;
- report likely causes;
- do not modify scientific parameters unless explicitly instructed.

If scripts fail:

- fix only clear code/runtime defects required to complete the requested task;
- do not change scientific setup unless explicitly instructed;
- report the failure and minimal fix.

If Codex believes scientific parameter tuning is needed and no autonomous
scientific authority was granted:

- stop after the current run;
- write a short recommendation;
- wait for user approval.

## Authorized autonomous research campaigns

When `AUTONOMOUS RESEARCH CAMPAIGN AUTHORIZED` is active, Codex may perform
scientifically legitimate development revisions without stopping for every
change, but only within the frozen scientific contract.

If a formal held-out study fails:

- preserve it;
- do not tune directly on that held-out set;
- return to development;
- version revisions;
- preregister a fresh held-out study before formal reevaluation.

If the same phase repeatedly fails an explicitly defined audit/repair cycle
limit, stop with the campaign's required blocked status.

Do not keep adding heuristics indefinitely merely to force a PASS.

---

# Reproducibility

Every experiment must preserve:

- config file used;
- command used;
- output paths;
- summary metrics;
- seeds;
- whether source code changed;
- whether configs changed;
- whether scientific assumptions changed.

Do not overwrite previous important results without creating a clearly named new
output directory or timestamped/versioned copy.

Formal, exploratory, smoke, oracle, and historical results must remain
distinguishable.

---

# Evidence Categories

Keep evidence categories distinct.

Recommended categories:

- **exploratory**:
  preliminary investigation; may guide development but is not formal evidence;

- **smoke**:
  mechanical/software validation only; not a scientific conclusion;

- **formal**:
  preregistered scientific experiment executed under an approved contract;

- **held-out**:
  formal evaluation cases not used for tuning the evaluated version;

- **oracle**:
  explicitly non-deployable reference condition using hidden/true quantities;

- **authoritative**:
  reviewed formal evidence promoted under the repository artifact policy.

Do not present exploratory, smoke, deterministic repeat, or oracle evidence as
independent deployable robustness evidence.

---

# Scientific Result Classification

By default, Codex should report observed metrics and avoid inventing its own
scientific labels.

However, when the current user prompt or approved Experiment Spec explicitly
defines labels such as:

- PASS / FAIL / INCONCLUSIVE;
- Phase A / B / C outcomes;
- `PHASE_3_READY`;
- `BLOCKED_*`;

Codex may and should assign exactly those predefined labels according to the
frozen criteria.

Codex must not redefine the label criteria after seeing results.

---

# Experiment Specs and Master Contracts

For research-workflow tasks:

- an approved Experiment Spec or Master Contract is the direct scientific
  contract;
- if it conflicts with informal suggestions or historical convenience, follow
  the approved current contract unless doing so violates a higher-level safety or
  repository rule;
- a Master Contract may explicitly authorize autonomous phase progression.

When a contract is marked immutable for a campaign:

- do not modify it to achieve PASS;
- clerical corrections must be separately documented;
- scientific changes require human approval or a new versioned contract.

---

# Usage Efficiency

Minimize unnecessary agent and tool usage, but never trade away scientific
correctness, reproducibility, safety, independent audit, or required validation
to save usage.

For long-running terminal commands:

- estimate runtime from prior runs, logs, configuration, or workload size;
- use adaptive sparse polling;
- check roughly every 30–60 seconds for 1–5 minute jobs;
- every 1–2 minutes for 5–15 minute jobs;
- every 3–5 minutes for longer jobs;
- increase polling interval when repeated checks show no meaningful change;
- poll every few seconds only when rapid interaction/error handling is genuinely
  required;
- prefer progress markers, completion signals, or concise log tails over
  repeatedly reading unchanged full output.

Escalate validation from cheapest/narrowest relevant checks to broader tests only
when justified.

Inspect enough repository context to ground the task, then reuse unchanged
findings.

Prefer targeted searches and focused reads over repeatedly rescanning the entire
repository.

Keep progress updates concise and meaningful.

If an autonomous campaign reaches a genuine blocked condition, do not burn usage
on speculative work outside the contract.

---

# Quota / Context / Interruption Handling

For long autonomous campaigns, maintain persistent state in repository files
rather than relying only on chat context.

If quota, model limits, context compaction, terminal interruption, or environment
failure prevents completion:

- save current phase;
- save completed work;
- save open findings;
- save exact remaining next action;
- save experiment provenance;
- save current git state.

Stop cleanly with the campaign-defined blocked/checkpoint status.

Never lower scientific requirements because quota is running low.

---

# Literature and External Research

When the current task authorizes literature/web research, Codex may use external
scientific literature and official documentation to guide methodology.

Prefer:

- original peer-reviewed papers;
- publisher pages;
- author preprints/arXiv;
- official hardware documentation;
- official software documentation.

Search snippets, blogs, and secondary summaries may be used for discovery but
should not be treated as primary scientific evidence.

For sources materially influencing design, preserve:

- title;
- authors;
- year;
- venue;
- DOI and/or canonical URL;
- exact claim used;
- relevance;
- limitation;
- design decision influenced.

Never fabricate citations, DOI values, paper results, or hardware capabilities.

Literature may influence HOW the approved problem is solved.

Literature must not silently weaken WHAT the approved scientific contract
requires.

---

# MPC Comparison Rules

Fixed MPC, adaptive MPC, and future robust/safe/learning-assisted MPC should
share the same base task, base cost interpretation, and base constraints when
the comparison is intended to isolate adaptation/learning effects, unless the
approved experiment explicitly defines another controlled comparison.

Do not make one method look better by silently changing:

- cost;
- constraints;
- horizon;
- optimizer;
- solver;
- task;
- physical parameters;
- evaluation duration.

Any deliberate difference must be preregistered and reported.

---

# Dynamics Rule

Do not modify verified Spring2D dynamics unless the current prompt explicitly
asks for dynamics changes.

For later Human V2 / CR12 work, verified historical plant/model artifacts must
also remain unchanged unless the current task explicitly authorizes a model
change and the change is versioned rather than rewriting historical evidence.

---

# Branch / Git Discipline

Unless explicitly authorized:

- do not create or switch branches;
- do not commit;
- do not push;
- do not merge;
- do not reset;
- do not stash;
- do not delete unrelated files.

If the current prompt explicitly authorizes creation/switching of a campaign
branch, Codex may do so.

Before changing branches or beginning a long campaign:

- record current branch;
- record HEAD;
- record `git status --short`;
- inventory pre-existing dirty/untracked files.

Pre-existing dirty state must be preserved.

Do not treat pre-existing dirty files as campaign changes.

Never use `git add .`.

Do not stage, commit, or push unless the prompt separately authorizes those exact
actions.

---

# Historical Evidence Protection

Do not modify historical authoritative results, old Stage scientific result
artifacts, or historical reports merely to align them with a new architecture.

When old code must be inspected or reused:

- preserve historical evidence;
- prefer new versioned implementations;
- write new result directories;
- document compatibility differences.

Do not retroactively relabel old experiments as proving a broader claim than
their original setup supported.

---

# Stage Research Workflow

Historically:

`stages/stage4_adaptive_control/docs/research/CURRENT_STATE.md`

is an entry point for Stage-4 research state.

For Stage-5 or architecture-recovery tasks, also inspect the relevant Stage-5
docs, configs, code, previous reports, and repository history named by the
current task.

Do not assume Stage-4 CURRENT_STATE alone defines the present Stage-5 scientific
contract.

For autonomous architecture-recovery campaigns, the campaign Master Contract
takes precedence over historical convenience, while historical documents remain
evidence about original intent and scope drift.

---

# Hardware Boundary

Simulation/offline authorization never implies physical-hardware authorization.

Without separate explicit user authorization, Codex must not:

- send commands to CR12;
- actuate a robot;
- enable torque/position/impedance/force-control hardware modes;
- move a mechanical leg;
- operate a physical F/T-controlled setup;
- conduct human testing.

Codex may inspect hardware SDKs, documentation, example code, logs, recorded
data, and create non-actuating integration code when authorized.

Do not claim hardware real-time readiness, hardware safety, clinical safety, or
patient suitability based solely on simulation.

---

# Reporting

At the end of each task, report:

- files changed;
- commands run;
- tests/checks;
- runs passed/failed/blocked;
- key metrics;
- bad or unexpected results;
- scientific variables changed;
- scientific variables explicitly unchanged;
- whether assumptions changed;
- whether parameters/configs changed;
- whether anything was staged, committed, pushed, reset, or deleted.

For an autonomous campaign, additionally report:

- starting branch/HEAD;
- campaign branch;
- phase reached;
- phase-gate outcomes;
- Auditor findings;
- repair cycles;
- formal experiments performed;
- held-out discipline;
- truth-firewall status;
- exact terminal status;
- exactly one recommended next step.

A scientifically valid blocked result is an acceptable final result.

## Full-3D Autonomous Closed-Loop Recovery v1 campaign authorization

For this campaign only, read `stages/stage5_personalized_motion_learning/docs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/TASK_CONTRACT.md` and `STATE.json` before work. The user authorizes continuous local simulation diagnosis, controller/model/estimator/reference/computation revisions and frozen validation within the shared six-hour, 1000-rollout, three-qualification-batch budget. Earlier four-repair, reference-only, manual-run and local-fix-then-stop restrictions do not apply to this campaign. Preserve task/safety/plant definitions, the 100 ms expiration rule, truth firewall, historical evidence and startup dirty state. No hardware actuation or Git mutation. One production writer; independent Auditor is read-only on production. Only the active coordinator may dispatch continuation; never recursively start a coordinator. STOPPED_BY_USER and resource limits prevent restart. The verbatim versioned contract governs details; historical clauses above remain intact.

### Overnight budget amendment (same campaign)

The user extended the shared cumulative active-time limit from six to twelve hours; this does not reset elapsed time. The authoritative TASK_CONTRACT.md amendment and STATE.json record the original start 2026-09-24T14:50:03Z and conservative cutoff 2026-09-25T02:50:03Z. The shared 1000-rollout and three-qualification-attempt limits remain unchanged. The earlier six-hour phrase above is historical; the six-hour point is a saved checkpoint, not a stop.
