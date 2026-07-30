# Research Execution Workflow

This workflow separates research decisions from implementation and preserves the distinction between validation work and scientific evidence. The current entry point is [CURRENT_STATE.md](CURRENT_STATE.md).

## Roles

- **Research and experiment-planning dialogue**: frames the research question, mechanism hypothesis, and Experiment Spec; evaluates formal results against the approved spec and returns PASS/FAIL/INCONCLUSIVE.
- **Learning dialogue**: supports concepts, derivations, code understanding, and reverse engineering.
- **Codex**: implements approved increments, adds logging, runs tests and explicitly authorized smoke checks, and reports metrics and mechanical completeness only.
- **User**: reviews diffs and the research dialogue's judgment, runs formal experiments manually, and decides result promotion, continuation, local modification, or branch closure.

## Experiment lifecycle

1. Research question
2. Mechanism hypothesis
3. Draft Experiment Spec
4. Human approval
5. Implementation
6. Tests and smoke validation
7. User formal run
8. PASS/FAIL/INCONCLUSIVE review
9. Result promotion or branch closure

## Evidence levels

| Level | Meaning | Permitted use |
|---|---|---|
| exploratory | Preliminary investigation or diagnosis. | Inform a draft spec; do not support formal claims or overwrite curated evidence. |
| smoke | Small, explicitly scoped mechanical validation. | Verify wiring, parsing, row counts, or basic invariants; do not draw scientific conclusions. |
| formal | User-run execution of an approved spec with recorded provenance. | Submit for human review; not authoritative until reviewed and promoted. |
| authoritative | Reviewed formal evidence retained under repository policy. | Support repository findings and downstream comparisons. |

Authoritative promotion requires all of the following:

- an approved Experiment Spec;
- a clean or explicitly recorded Git state;
- the exact command;
- resolved configuration and provenance;
- the complete expected experiment matrix;
- user-run formal execution;
- a reviewed conclusion.

Artifact retention, output placement, and authoritative-result rules are defined in [results/README.md](../../results/README.md). That policy takes precedence over this workflow's brief evidence-level summary.
