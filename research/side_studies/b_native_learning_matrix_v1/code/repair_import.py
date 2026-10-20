from task_bootstrap import *
p=STUDY/'code/inspect.py'
if p.exists():p.rename(STUDY/'reports/inspect_shadowing_failed_v1.py.txt')
save(STUDY/'reports/REPAIR_01.json',dict(unix=time.time(),cause='New helper named inspect.py shadowed Python standard library inspect during numpy/scipy imports',fix='Rename helper source_peek.py; preserve failed source and attempts; no physical/controller/task changes',affected_attempts=['000_original_B','001_zero_interface']))
from prepare import enqueue
enqueue('002_original_B_retry1',original=True)
enqueue('003_zero_interface_retry1')
