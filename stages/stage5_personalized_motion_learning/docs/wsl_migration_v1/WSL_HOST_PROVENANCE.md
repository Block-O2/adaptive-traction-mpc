# WSL host provenance

- Captured: 2026-09-29T00:21:52+08:00
- Host: LENOVO model 83DF, Windows 10.0.26200 build 26200
- WSL: 2.6.3.0, Ubuntu 24.04.3 LTS, kernel 6.6.87.2-microsoft-standard-WSL2
- CPU: Intel(R) Core(TM) i9-14900HX, 32 logical CPUs; default affinity 0-31; nice 0
- WSL RAM: 8176918528 bytes observed; swap 2147483648 bytes
- GPU visibility: NVIDIA GeForce RTX 4060 Laptop GPU, Windows driver 560.94, WSL CUDA bridge 12.6; not used to alter the scientific code path
- Repository filesystem: /home/hank/coding/adaptive-traction-mpc-learning on /dev/sdd (ext4); `/mnt/c` was not used for benchmark execution
- Power/background: Windows Balanced plan, battery status code 2, 97% charge; Windows background interference was recorded but not controlled
- Procedure: unchanged default affinity and priority for all 24 runs; `OPENBLAS_NUM_THREADS=1`; no hard-real-time claim
- Per-run host evidence: start timestamp and load average are present. Process CPU percent and memory-used snapshots are unavailable because the frozen runner did not instrument them.
