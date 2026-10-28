"""Frozen root entry point; collection only, no optimizer or physics on import."""
from pathlib import Path
import os,sys
sys.path.insert(0,str(Path(os.environ['ACL2_PACKAGE'])/'families/ppo_reward'))
from onpolicy_sequence_v1 import sequence
