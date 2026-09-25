# Preserved representative batch-status extraction error

`representative_v1/batch_status.json` was emitted by the first development
runner version with `commissioning_completed` extracted from a nonexistent
`summary["commissioning"]["completed"]` field, so it incorrectly reports
`false` for all four cases. The original per-case `summary.json` contains a
complete commissioning object, about 7.02 s duration, and full subsequent
recovery/task data. The runner extraction was corrected *before* the broad
batch; the original representative artifact was not overwritten. The broad
batch and read-only `review_v1/DEVELOPMENT_SUMMARY.json` derive commissioning
completion from the actual summary object and report 22/22. This is a
reporting/extraction bug, not a control or physics change.
