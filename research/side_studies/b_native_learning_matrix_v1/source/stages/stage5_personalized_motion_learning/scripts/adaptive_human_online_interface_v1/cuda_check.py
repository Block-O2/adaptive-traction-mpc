from pathlib import Path
import sys,json,subprocess,importlib.metadata
import torch
D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/source/stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1')
ready=torch.cuda.is_available()
record=dict(status='CUDA_READY' if ready else 'CUDA_NOT_READY',python=sys.version,executable=sys.executable,torch_version=torch.__version__,torch_version_cuda=torch.version.cuda,torch_cuda_is_available=ready,device_name=torch.cuda.get_device_name(0) if ready else None,nvidia_smi=subprocess.check_output(['nvidia-smi'],text=True),packages={p:importlib.metadata.version(p) for p in ('torch','gymnasium','stable-baselines3','sb3-contrib','ruckig','numpy','mujoco')},isolation='new venv with frozen physical dependencies inherited read-only; GPU/RL packages installed only in new venv',physics_device='unchanged CPU MuJoCo',training_steps=0)
if ready:
    x=torch.ones((64,64),device='cuda');record['cuda_tensor_smoke_sum']=float((x@x).sum().item())
(D/'CUDA_RL_ENV_READINESS.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('status','torch_version','torch_version_cuda','torch_cuda_is_available','device_name')}))
