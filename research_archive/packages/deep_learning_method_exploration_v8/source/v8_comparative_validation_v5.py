"""Frozen comparison: original V3 core, Beta means before remaining grid.

Separate actual inventory, source/config freeze and physics approval required.
"""
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(os.environ["ACL2_PACKAGE"]) / "families/ppo_reward/continuous_scale_v1"))
from comparative_composer_v4_candidate_v3 import sequence
