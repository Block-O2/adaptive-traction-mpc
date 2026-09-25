# Full-3D startup DGN V1 — restart checkpoint

Date: 2026-09-23. Terminal diagnostic status: **DGN_COMPLETE**. Stop here;
DEV, new QUAL, ROM extension and value learning have **not** begun.
Current branch `codex/stage5-architecture-recovery`, HEAD
`bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`. At entry,
`git status --short --untracked-files=all` listed 566 pre-existing dirty/untracked
paths, including unrelated Stage-4 and the uncommitted full-3D implementation.
None has been staged, committed, reset, stashed, deleted or pushed in DGN.

The failed 24-case × 3-arm fresh qualification is historical formal evidence;
this DGN may inspect its cases as *development diagnostics* only. Its files,
seeds, gates and metrics remain unchanged. See sibling
`fresh_qualification_v1/{FORMAL_RESULT_REPORT,PREREGISTRATION,FINAL_AUDIT,STATUS}.md`.
The frozen source/config/model/native dependency manifest is the sibling
`FREEZE_MANIFEST.json` (SHA-256
`8545edac3f6d2febbac1c129fc86021a3547b96c5d62dbeae41d23d84044fa9c`;
309 paths). `SOURCE_SNAPSHOT.md` records targeted local hashes before any
DGN tooling. The local implementation, not published HEAD alone, is the
diagnostic subject.

Completed read-only baseline analysis: five aligned episode plots in
`results/.../startup_dgn_v1/aligned_existing_traces_v2/`; 24-case adaptive
handoff census in `handoff_population_v2.json`. The earlier `*_v1` plot output
misrepresented the unexecuted terminal boundary's zero command and is
superseded, not deleted. The three shared pre-step exceptions were reproduced
with the unchanged initializer in `prestep_initialization_replay_v1.json`:
loaded CR12 IK succeeded, then nominal-geometry measured initial support was
more than 1 degree behind task start and rejected by the task-waypoint
progress predicate.

Focused physical development replays: `contact_replay_balanced_ordinary_r01`
and `contact_replay_nominal_development` added evaluation-only 0.25 ms
shank/bed normal-force telemetry. All compared commissioning trace arrays
matched historical runs exactly (maximum absolute difference zero). Both
had material temporary contact, but the failed-case true/reference angular
error exceeded 1 degree before contact. A further unchanged physical replay,
`fit_information_balanced_ordinary_r01`, copied deployable fitting inputs:
352 samples, data-only geometry Jacobian condition ~1393 vs augmented
regularized ~1337; 56/351 retrospective dynamics update intervals overlapped
physical bed contact. These replays are development diagnostics, never fresh
held-out evidence or a runtime qualification. No production implementation,
scientific parameter, task, threshold or historical formal artifact changed.

Deliverables: `DGN_REPORT.md`, one coherent `DEV_DECISION_PLAN.md`,
`COMMANDS.md`, this checkpoint, source snapshot/protocol and the independent
fresh-context `AUDIT_REPORT.md`. The Auditor independently recomputed all
309 frozen dependency hashes, 72 formal outcomes, 21 contact/event-order
traces, 17 handoff medians, two contact-replay integrals and exact trace
comparisons. Initial F1–F4 wording/scope findings were corrected and retained
in the audit history; final independent diagnostic audit **PASS**. The open
physical tracking-error decomposition and deployable shank-length/contact
policy are explicitly documented, not invented as resolved.

Final local checks: five new diagnostic Python scripts compiled under
`mpc_learn` with `PYTHONPYCACHEPREFIX=/private/tmp/full3d_startup_dgn_v1_pycache`;
all new DGN JSON files passed `jq empty`; `git diff --check` passed (tracked
diffs only). Branch and HEAD remained
`codex/stage5-architecture-recovery` / `bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce`.
Ending `git status --porcelain=v1 --untracked-files=all` has 578 entries:
566 pre-existing unrelated/earlier-campaign dirty or untracked paths and
12 new DGN docs/scripts. DGN result artifacts exist locally under
`results/.../startup_dgn_v1/` and are ignored by Git; no clean-clone
reproducibility is claimed. Nothing was staged, committed, pushed, reset,
stashed, deleted or switched.

Exactly one recommended next step: open a separately versioned DEV lifecycle
repair, beginning with the matched retained-model active-recovery versus
single justified update comparison in `DEV_DECISION_PLAN.md`; do not treat
the present diagnosis as controller qualification.
