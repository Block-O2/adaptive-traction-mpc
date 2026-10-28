"""Thin entry for separately approved continuous-Beta sampling; no fit here."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(os.environ['ACL2_PACKAGE']) / 'families/ppo_reward/continuous_scale_v1'))
from beta_sampling_sequence_candidate_v1 import sequence
