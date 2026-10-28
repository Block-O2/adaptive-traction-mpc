# Cloud environment audit

Observed host: `ubuntu-32gb-fsn1-2`, user `hank`. Ubuntu 24.04.4, Python 3.12.3, 8 logical CPUs / 4 presented cores with SMT. Host total RAM 30.60 GiB; no swap. Original free disk about 213 GiB. Final available disk 208.96 GiB.

The uploaded ZIP was used exclusively; all 450 original manifest payloads passed before execution. The original ZIP and SHA256_MANIFEST.json remain intact. All scientific files under source/ match that manifest. Documented cloud wrapper/resource/audit changes are in PACKAGE_VERIFICATION.json and deployment_audit/DEPLOYED_SOURCE_MANIFEST.json.

CPU versions: MuJoCo 3.10.0, Torch 2.7.1+cpu, NumPy 2.2.6, SciPy 1.15.3, Gymnasium 1.1.1, SB3 2.6.0. All requirements pins match installed metadata; pip check PASS. Torch CUDA build is None. Python minor version matches local 3.12; patch differs from reported WSL 3.12.14. No cross-platform bitwise parity is claimed.

The initial venv command lacked ensurepip. A public pip 25.2 wheel was downloaded using PyPI metadata and verified against its SHA256, then installed only into .venv. install.sh was read before any dependency installation and was not blindly executed. The fixed CPU requirements were installed directly. No CUDA/NVIDIA packages were installed.

A normal `sudo -n apt-get` attempt required an interactive password and made no system changes. The user reported installing the prerequisites. The recorded on-host dpkg query at 2026-10-20T06:25:29.142574+00:00 still reported libgl1/libegl1/libglfw3 absent and python3.12-venv not installed. Headless real MuJoCo model loading and integration nevertheless succeeded; these optional rendering/venv-bootstrap OS packages are not falsely reported installed. Raw status is in deployment_audit/ENVIRONMENT_SNAPSHOT.json.

Runtime protection was raised to 6 GiB available RAM, with 7.25 GiB admission; exact boundary tests PASS. Every physics process had a 600 s cap, every diagnostic episode a 128-decision cap, and at most two physics processes ran. Long-training profiles remain disabled. No SSH, network, firewall, power, sudo configuration, server sizing or Git mutations occurred.

Measured minimum available RAM 28.472 GiB; no swap growth, OOM, MuJoCo warnings or disk stop observed. A saved-JSON reader reached its own 16 MiB parser limit once; this was an analysis error, not memory exhaustion.
