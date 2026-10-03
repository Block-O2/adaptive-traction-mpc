# Future research data lifecycle policy

At campaign closeout, create REPORT.md, SUMMARY.json, ALL_RUNS.csv/json, MANIFEST.json, FIGURES/, SELECTED_TRACES/ and CHECKPOINTS/. Include failed and infeasible attempts in the aggregate tables. Record source commit, frozen configs, environment, seeds, exact commands and immutable artifact hashes.

Classify every raw artifact as KEEP_RAW, ARCHIVE_RAW or DISCARDABLE_RAW, with an explicit reason and downstream dependency list. KEEP_RAW includes canonical checkpoint inputs, held-out evidence and a small representative baseline/best/neutral/worse/failure trace set. ARCHIVE_RAW includes complete historical rollouts and intermediate evidence that remains scientifically useful. DISCARDABLE_RAW includes reproducible caches only, or explicitly documented temporary products with no unique scientific content.

Keep the current experiment and minimal scientific evidence in active WSL. Store full historical raw archives under the established D:\CodexResearchEvidence\adaptive-traction-mpc-learning parent. Keep source, configs, contracts, reports, compact summaries and manifests in Git. Store bulky raw outside Git while preserving provenance and restoration recipes.

Close active writers and verify clean, pushed Git history before archive closeout. Check D: free space and preserve max(100 GB, 15% of capacity), allowing for its Windows pagefile. Copy directly to D: without a second C: staging copy. Reuse trustworthy raw manifest hashes, verify destination file count and SHA256, and record an exact deletion manifest. Never delete tracked files or change a frozen report/config during cleanup. Ambiguous checkpoint dependencies require retention.

Do not treat logical WSL free space as Windows C: capacity. Measure host free space before large campaigns. Compaction must use a supported offline method against the confirmed active VHDX after WSL shutdown. Do not launch large campaigns until adequate C: headroom is actually measured. Start with one rollout worker; larger concurrency needs measured peak-memory and host-storage evidence.

This cleanup task makes no research-script or resource-configuration changes. Implementation of streaming traces, telemetry and closeout automation belongs in a separately authorized development task.
