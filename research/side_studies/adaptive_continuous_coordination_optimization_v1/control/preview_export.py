from pathlib import Path
import shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
shutil.copytree(P/'figures',L/'figures',dirs_exist_ok=True)
for n in ['DIAGNOSTIC_RESULTS.json','CORRELATION_SENSITIVITY.json','ADAPTIVE_REFINEMENT_PLAN.json']:
 shutil.copy2(P/n,L/n)
print('READ_ONLY_PREVIEW_EXPORTED')
