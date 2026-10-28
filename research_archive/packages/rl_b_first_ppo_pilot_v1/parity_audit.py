"""Independent streamed old/new physical parity. Evaluation truth only."""
from pathlib import Path
from itertools import zip_longest
import math,json
from stream_json import array_items
from common import put

def compare(old,new,out):
 result={'category':'INDEPENDENT_REPLAY_PARITY_AUDIT','old':str(old),'new':str(new),'arrays':{}}
 groups={'trace':['time_s','task_phase','q_ref_rad','dq_ref_rad_s','ddq_ref_rad_s2','estimated_state','truth_state','cuff_force_world_n','cuff_moment_world_nm','applied_robot_tau_nm'], 'native_states_evaluation_only':['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only'],'command_receipts':['applied','native_steps','start_physics_s','end_physics_s','source_sample_time_s','command_torque_nm']}
 def delta(a,b):
  if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
   if math.isnan(a) and math.isnan(b):return 0.
   return abs(a-b)
  if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):return max([delta(x,y) for x,y in zip(a,b)],default=0.)
  return 0. if a==b else math.inf
 for name,keys in groups.items():
  count=0;maxima={k:0. for k in keys};mismatches=[];missing=[]
  for i,(a,b) in enumerate(zip_longest(array_items(old,name),array_items(new,name))):
   count+=1
   if a is None or b is None:mismatches.append({'row':i,'reason':'row_count'});continue
   for k in keys:
    if k not in a or k not in b:
     if (k in a)!=(k in b):missing.append({'row':i,'key':k})
     continue
    d=delta(a[k],b[k]);maxima[k]=max(maxima[k],d)
    if d>1e-12 and len(mismatches)<12:mismatches.append({'row':i,'key':k,'max_abs_diff':d})
  result['arrays'][name]={'rows':count,'max_abs_diff':maxima,'mismatches_first12':mismatches,'missing_asymmetry_first12':missing[:12],'pass':not mismatches and not missing,'tolerance':1e-12}
 result['pass']=all(x['pass'] for x in result['arrays'].values());put(out,result);print(out,result['pass'],{k:(v['rows'],v['mismatches_first12']) for k,v in result['arrays'].items()});return result
if __name__=='__main__':
 import sys
 compare(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
