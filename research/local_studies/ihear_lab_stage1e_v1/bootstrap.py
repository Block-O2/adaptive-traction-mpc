"""Stage1E imports: read-only Stage1D kernel and original native modules."""
from pathlib import Path
import sys
P = Path(__file__).resolve().parent
R = P.parents[2]
D = R / 'research/local_studies/ihear_lab_stage1d_v1'
sys.path.insert(0, str(D))
for stage in ('stage3_full3d', 'stage4_adaptive_control', 'stage5_personalized_motion_learning'):
    sys.path.insert(0, str(R / 'stages' / stage / 'src'))
sys.path.append(str(R / 'research/local_studies/ihear_lab_stage1b_v1/deps'))
