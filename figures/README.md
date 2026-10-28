# Evidence figures

New archive figures are rendered only from the retained original arrays and update receipts. Run `python rebuild_archive_evidence.py --source-root /path/to/repository/research_archive/packages --output-dir /tmp/ihear-evidence` to regenerate the PNG/SVG/PDF figures, CSV tables, and numerical cross-check receipt. This program does not train, roll out physics, or alter original research packages.

The PPO chart contains two recorded fresh on-policy batches, with three optimization epochs each. It is an update diagnostic, not a long training convergence curve or an independent validation result. The full-task trajectory chart displays every native position sample; wrench is the original 5 ms measured stream. The derivative chart uses every original unfiltered native jerk sample.
