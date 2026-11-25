# Research evolution

| Stage | What changed | Evidence that can support a claim |
| --- | --- | --- |
| Fixed reference and goal-directed torque MPC | A prescribed motion reference gave way to goal-directed constrained torque optimization on the coupled plant. | Stage-specific simulation configurations and the matched comparisons described in the root README. |
| Controller B | A finite set of waypoint proposals is screened and selected at decision events. The selected reference passes through the original execution and safety interfaces. | Frozen B traces, command receipts, task contract and scorer define the baseline. |
| D and D-U | Larger computation budgets support predictive optimization over a continuous action space. | Interpret outcomes within the corresponding arm, Human condition, budget and motion qualification. |
| RT2 and BG | Lower-cost reference construction, receipt ownership and the boundary between proposal and activation were tested against frozen B. | Offline scoring and moving-window replay can establish software equivalence within the recorded windows. |
| FGDW-v1 | An analytical force-guided proposal was passed to the original reference interface. | **NO-GO** at the fixed-quintic coefficient requirement. There was no physical comparison. |
| FGDW-I | Exponential reference segments, continuous geometric certification and stopping constructions were studied. | **LIMITED** under calibration uncertainty. The evidence applies to the interface study. |
| FGDW-I-R | Matched-B certification, exact computational reuse and timing diagnostics were separated. | Matched-B certification **GO**. Full certification within the computation budget **NO-GO**. |

The local research archive retains qualified comparisons, necessary raw evidence,
negative outcomes and compact historical tables. Some exploration event streams
and training states were retired after closeout. A preserved table can substantiate
its reported metric. An independent rescore requires the original samples, versioned
scorer and the matching contract. The archive freeze tag identifies the earlier
committed repository tree. Unpublished inputs and local recovery records have
separate identities.

See [current research and reproduction](CURRENT_RESEARCH.md) and the
[logging standard](EXPERIMENT_LOGGING_STANDARD.md).
