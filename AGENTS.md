# AGENTS.md

## Project Scope

This repository is for adaptive traction MPC experiments. The goal is to develop and compare fixed MPC, online identification, adaptive MPC, and later robust/safe adaptive MPC in a controlled and reproducible way.

## Execution Discipline

Codex must execute only the task described in the user's prompt.

Do not make extra scientific, algorithmic, or parameter changes unless the prompt explicitly asks for them.

In particular, do not independently:
- tune controller parameters because results look bad
- change cost weights
- change constraints
- change physical parameters
- change noise or bias settings
- change target angle
- change optimizer settings
- change solver settings
- change max_time, max_steps, or effective rollout duration
- add gravity compensation
- add hidden clipping or hidden safety logic
- replace the algorithm
- add new experiments
- remove failed results
- hide or overwrite unfavorable outputs

Bad results are valid experimental results.

Treat exploratory runs as exploratory only. Do not fold exploratory tuning back into configs or code unless the user explicitly approves that exact change.

If a run fails, gets stuck, violates constraints, or produces poor performance, Codex must report the issue instead of silently fixing it.

## Usage Efficiency

Minimize unnecessary agent and tool usage, but never trade away scientific correctness, reproducibility, safety, or required validation to save usage.

- For long-running terminal commands, estimate runtime from prior runs, logs, configuration, or workload size and use adaptive sparse polling. Check roughly every 30–60 seconds for 1–5 minute jobs, every 1–2 minutes for 5–15 minute jobs, and every 3–5 minutes for longer jobs; increase the interval when repeated checks show no meaningful change. Poll every few seconds only when rapid interaction or immediate error handling is genuinely required. Prefer progress markers, completion signals, or concise log tails over repeatedly reading unchanged full output.
- Escalate validation from the cheapest, narrowest relevant check to broader tests only when justified by the change, a failure, repository policy, or the user's request. Do not skip checks required for scientific correctness or reproducibility.
- Inspect the repository enough to ground the task, then reuse unchanged findings. Prefer targeted searches and focused reads over repeatedly scanning the same files or the entire repository.
- Keep intermediate updates concise and send them only for meaningful progress, decisions, failures, or long waits; avoid narrating routine tool calls or repeating unchanged status.
- Use a single agent by default. Do not create subagents or parallel work unless the user requests them or independent work clearly provides necessary value that outweighs the added usage and coordination cost.
- When progress depends on a user decision, new scientific authority, or a meaningful scope choice, summarize the evidence and stop for approval instead of spending usage on speculative implementation, tuning, experiments, or broad exploration.

## Required Behavior When Results Look Bad

If results are poor but scripts complete:
- save the outputs
- summarize what happened
- report likely causes
- do not modify parameters unless explicitly instructed

If scripts fail:
- fix only clear code/runtime errors required to complete the requested task
- do not change the scientific setup unless explicitly instructed
- report the failure and the minimal fix applied

If Codex believes parameter tuning is needed:
- stop after the current run
- write a short recommendation
- wait for user approval before changing parameters

## Reproducibility

Every experiment must preserve:
- config file used
- command used
- output paths
- summary metrics
- whether any source code or config was changed

Do not overwrite previous important results without creating a clearly named new output directory or timestamped copy.

## MPC Comparison Rules

Fixed MPC, adaptive MPC, and future robust/safe adaptive MPC must share the same base cost and base constraints unless the user explicitly asks otherwise.

Safe/robust adaptive MPC may only differ by uncertainty-aware tightening or safety logic explicitly requested by the user.

Do not make one method look better by changing its cost, constraints, horizon, optimizer, or physical parameters.

## Dynamics Rule

Do not modify verified Spring2D dynamics unless the prompt explicitly asks for dynamics changes.

## Reporting

At the end of each task, report:
- files changed
- commands run
- whether runs passed or failed
- key metrics
- any bad or unexpected result
- whether any parameter/config/scientific change was made

## Research Workflow Guardrails

`docs/research/CURRENT_STATE.md` is the entry point for the current research state. Read it before beginning a research-workflow task.

An approved Experiment Spec is the direct contract for implementation. If it conflicts with general suggestions or informal discussion, follow the approved spec.

Keep evidence categories distinct:

- **exploratory**: preliminary investigation; not a basis for formal claims or result promotion;
- **smoke**: mechanical implementation validation only; not a scientific conclusion;
- **formal**: user-run execution of an approved Experiment Spec, awaiting review;
- **authoritative**: reviewed formal evidence promoted under the repository artifact policy.

Codex may run unit tests, compile checks, and explicitly authorized smoke tests only. Codex must not run a full or formal scientific experiment; the user runs formal experiments manually. Smoke or local outputs must not be written to, or overwrite, an authoritative result directory.

Codex must not independently label a scientific result PASS, FAIL, or INCONCLUSIVE. Report observed metrics and whether mechanical completeness checks passed.

Do not modify historical authoritative results or old Stage scientific scripts unless the prompt explicitly names the file and explains the reason. Before editing, confirm the baseline, the single variable, allowed changes, and forbidden changes.

Unless explicitly authorized, do not commit, push, merge, delete files, or switch branches.

For a research-workflow task, finish by reporting:

- files changed;
- scientific variables changed;
- scientific variables explicitly unchanged;
- commands run;
- tests/checks;
- unexpected findings;
- formal command reserved for the user.
