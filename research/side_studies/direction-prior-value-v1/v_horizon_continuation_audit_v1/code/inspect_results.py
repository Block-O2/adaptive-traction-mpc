"""Compact read-only results inspection for unattended monitoring."""
from freeze import *
import sys
def main():
 for name in sys.argv[1:]:
  if name.startswith('batch:'):
   batch=name.split(':',1)[1];rows=[];groups={}
   for q in sorted((STUDY/'queue').glob('*.json')):
    request=json.loads(q.read_text())
    if request.get('batch')!=batch:continue
    path=Path(request['result_path'])
    if not path.exists():continue
    r=json.loads(path.read_text());m=r.get('metric',{});qualified=bool(m.get('valid') and m.get('matched_eligible') and m.get('status')=='COMPLETE')
    row=dict(group=request['group'],method=request['method'],qualified=qualified,J_F=m.get('J_F'),M=m.get('moment_integral'),wall_s=r.get('wall_seconds'));rows.append(row);groups.setdefault(row['group'],{})[row['method']]=row
   paired=[]
   for group,methods in groups.items():
    if len(methods)!=4 or not all(r['qualified'] for r in methods.values()):continue
    base=methods['P'];paired.append(dict(group=group,force_gain_percent={m:100*(base['J_F']-r['J_F'])/base['J_F'] for m,r in methods.items()},moment_change_percent={m:100*(r['M']-base['M'])/base['M'] for m,r in methods.items()}))
   print(name,json.dumps(dict(completed=len(rows),qualified=sum(r['qualified'] for r in rows),complete_pairs=len(paired),latest_complete_pairs=paired[-2:],partial_monitor_only=True)));continue
  path=STUDY/name
  if not path.exists():print(name,'PENDING');continue
  data=json.loads(path.read_text())
  if name.startswith('ANALYSIS_'):
   result=dict(groups_complete=data.get('groups_complete'),eligible=data.get('eligible_pilot_methods'),methods={m:{k:r.get(k) for k in ('attempted','valid','mean_J_F_Ns','mean_paired_gain_fraction','mean_moment_integral_change_fraction')} for m,r in data['methods'].items()})
  elif name=='HELDOUT_SNAPSHOT_ANALYSIS.json':
   result=dict(complete=data.get('complete'),states=[dict(label=s['label'],unique=s['completed_unique'],methods=s['methods'],quality=s['quality']) for s in data['states']])
  elif name.endswith('TRAINING.json'):
   result={k:data.get(k) for k in ('device','V_counts','G_counts','V_selected','training_script_sha256','test_used','wall_s','peak_host_rss_bytes','CUDA_peak_allocated_bytes','metrics')}
  else:result=data
  print(name,json.dumps(result))
if __name__=='__main__':main()
