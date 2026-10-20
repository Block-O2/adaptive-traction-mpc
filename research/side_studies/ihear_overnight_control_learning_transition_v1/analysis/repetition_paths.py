"""Resolve original and uniquely named serializer-repair pilot evidence."""
from pathlib import Path
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1')
GROUP='REPR' if (P/'REPETITION_RETRY_PROTOCOL.json').exists() else 'REP'
def rep_path(name,group=GROUP):
    if group=='REP':return name
    if 'REPETITION_RETRY_' not in name:name=name.replace('REPETITION_','REPETITION_RETRY_')
    return name.replace('REP_','REPR_')
class RepeatRoot:
    def __init__(self,group=GROUP):self.group=group
    def __truediv__(self,name):return P/rep_path(name,self.group)
