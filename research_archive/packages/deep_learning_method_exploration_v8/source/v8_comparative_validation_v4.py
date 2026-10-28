"""Source-only frozen core-five and independent continuous-axis comparison.

Requires separate main-approved actual inventories/config and physical dispatch.
"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(os.environ["ACL2_PACKAGE"]) / "families/ppo_reward/continuous_scale_v1"))
from comparative_composer_v4_candidate_v2 import sequence
