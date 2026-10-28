"""Reviewed exposed-condition continuous-axis engineering gate."""
from pathlib import Path
import os, sys
sys.path.insert(0, str(Path(os.environ['ACL2_PACKAGE']) / 'families/ppo_reward/continuous_scale_v1'))
from gate1_sequence_candidate_v2 import sequence
