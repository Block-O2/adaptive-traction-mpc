from pathlib import Path
import sys
P=Path(__file__).resolve().parent
R=P.parents[2]
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0,str(R/'stages'/stage/'src'))
for stage in ('d','e','f'):
    sys.path.append(str(R/f'research/local_studies/ihear_lab_stage1{stage}_v1'))
sys.path.append(str(R/'research/local_studies/ihear_lab_stage1b_v1/deps'))
