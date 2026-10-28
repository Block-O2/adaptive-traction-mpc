"""N8 native complete raw tree; same keys, every dependency retained."""
from pathlib import Path
import sys
S=Path('/home/hank/ihear-lab/smoothness_critic_research_v5/runtime');INSTALLED=False
def install():
 global INSTALLED
 if INSTALLED:return
 sys.path.insert(0,str(S/'build'));import fast_native as n,loaded_context_reuse as reuse
 original=reuse.raw
 def raw(value):return n.raw_value_tree(value,original)
 reuse.raw=raw;INSTALLED=True;return original,raw
