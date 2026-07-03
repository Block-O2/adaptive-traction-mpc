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
