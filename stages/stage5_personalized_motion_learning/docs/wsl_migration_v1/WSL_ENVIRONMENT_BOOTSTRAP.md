# WSL2 environment bootstrap

Use Ubuntu in WSL2 on the Y9000P. Work at the repository root. Record `uname -a`, `cat /etc/os-release`, `wsl.exe --version` when available, CPU model, RAM, GPU driver/runtime, Python, MuJoCo and approximate host load. The Mac reference versions are in `REFERENCE_ENVIRONMENT.json`; they are observations, not a claim that identical binary wheels work across hosts.

Install a Python 3.10 environment (project metadata permits >=3.10; 3.10 matches the Mac reference). Example with an available Python 3.10 interpreter:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'mujoco==3.10.0' 'numpy==2.2.6' 'scipy==1.15.3' 'matplotlib==3.10.9' 'pytest==9.1.1'
python -m pip install -e './stages/stage5_personalized_motion_learning[dev]'
python -m pip install 'osqp==1.1.2' 'casadi==3.7.2'
```

The project metadata declares matplotlib, mujoco, numpy and scipy; Mac reference exact versions are 3.10.9, 3.10.0, 2.2.6 and 1.15.3 respectively. Optional OSQP/CasADi were observed on Mac and should be installed if an import path needs them. Gymnasium, SB3 and torch were absent in the reference environment; do not add them for this Stage-5 benchmark without a demonstrated dependency. Capture `python -m pip freeze` in WSL output. No compiler-specific runtime is required by the checked-in Stage-5 path beyond installed Python wheels; record actual C/C++ toolchain only if a source build is necessary.

For headless MuJoCo, use `MUJOCO_GL=egl` only after verifying WSL GPU/EGL; `MUJOCO_GL=osmesa` is a CPU fallback if available. The benchmark is CPU planner timing; record any rendering setting. Check `python -c 'import mujoco; print(mujoco.__version__)'`, `nvidia-smi` if NVIDIA is exposed, and load the CR12 XML. Do not infer GPU acceleration merely from a successful MuJoCo import.
