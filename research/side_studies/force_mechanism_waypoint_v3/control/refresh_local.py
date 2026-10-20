from pathlib import Path
import sys,textwrap
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3');sys.path.insert(0,str(P/'control'))
from analyze_mechanism import *
from plot_local_scale import visible_y_limits
original_save=save
def save(fig,name):
 for ax in fig.axes:visible_y_limits(ax)
 original_save(fig,name)
B=load('B0');E=load('18D');bounds=B['rec']['task_bounds_s'];cols=['#2166ac','#b2182b']
s=(P/'control/analyze_mechanism.py').read_text();a=s.index(" for lo,hi,tag in [(3.7,6.2");b=s.index(" print('ARCHIVE_ANALYSIS_COMPLETE'",a);s=textwrap.dedent(s[a:b]).replace('Allocated force norm','Total command force norm').replace('Allocated moment norm','Total command moment norm')
exec(compile(s,'local figure refresh, no physics','exec'))
print('LOCAL_LABELS_CORRECTED total command wrench distinguished from pure allocator')
