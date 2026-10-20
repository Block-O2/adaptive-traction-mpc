# Monitor repair and exact A restoration

The original orchestration incorrectly applied the 4.5 GiB process-tree gate unconditionally, including evaluation. The previously corrected monitor applies it only during training at >=55k steps, unreachable by either 50k arm. Real memory, commit, swap, external-process and wall-cap guards remain active. Original source and false-stop logs are retained.

Only this campaign's own A step-10000 checkpoint, optimizer, replay and RNG are restored. The open episode is reconstructed with its 419 prior actor actions; every observation, next observation, float32 reward and done flag must match bitwise. Reconstruction adds no online samples or updates. The outstanding standard update for the already collected step 10000 is performed once, then standard SAC learns exactly 40000 remaining steps. No teacher actions, prior scratch300k state, modified science, new budget or repeated B training.
