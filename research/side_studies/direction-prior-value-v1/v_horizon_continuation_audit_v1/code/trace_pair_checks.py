from audit_common import *
import numpy as np
FIELDS=('time_s','physics_steps','task_phase','reference_q_rad','reference_dq_rad_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','cr12_q_rad','cr12_dq_rad_s','physical_cuff_position_world_m','physical_cuff_rotation_world','physical_cuff_force_world_n','physical_cuff_moment_world_nm')
def path(r,base):
 p=Path(r['metric']['trace']);return p if p.is_absolute() else base/'source'/p
def compare(pa,pb,stop):
 with np.load(pa) as a,np.load(pb) as b:
  ma=a['time_s']<=stop+1e-8;mb=b['time_s']<=stop+1e-8;check={}
  for field in FIELDS:
   x,y=a[field][ma],b[field][mb];check[field]=bool(x.shape==y.shape and np.array_equal(x,y))
 return check
def main():
 outcomes=[read(p) for p in (STUDY/'output').glob('*_OUTCOME.json')];checks=[];divergences=[]
 for case in read(STUDY/'AUDIT_CONTRACT.json')['cases']:
  for item in case['candidates']:
   a=read(item['committed_source']) if item['committed_source'] else next((r for r in outcomes if r['child']['item']['identity']==item['identity'] and r['child']['mode']=='COMMITTED'),None)
   if a is None:continue
   ap=path(a,OLD if item['committed_source'] else STUDY)
   for mode in ('P_RECEDING','PV_RECEDING'):
    b=next((r for r in outcomes if r['child']['item']['identity']==item['identity'] and r['child']['mode']==mode),None)
    if b is None or len(b['events'])<2:continue
    stop=b['events'][1]['physical_time'];fields=compare(ap,path(b,STUDY),stop)
    checks.append(dict(state=case['state'],identity=item['identity'],mode=mode,through_next_modifiable_boundary_s=stop,fields=fields,pass_=all(fields.values())))
    original=np.asarray(item['plan']);first_action_change=None
    for event in b['events'][1:]:
     i=('OUTBOUND','RETURN').index(event['context']['phase']);j=event['count'][event['context']['phase']]
     if j<5 and not np.array_equal(np.asarray(event['selected_plan'])[i,j],original[i,j]):first_action_change=event;break
    with np.load(ap) as za,np.load(path(b,STUDY)) as zb:
     n=min(len(za['time_s']),len(zb['time_s']));diff=np.max(np.abs(za['reference_q_rad'][:n]-zb['reference_q_rad'][:n]),axis=1);idx=np.flatnonzero(diff>1e-12);physical_divergence=None if not len(idx) else float(za['time_s'][idx[0]])
    divergences.append(dict(state=case['state'],identity=item['identity'],mode=mode,first_current_K3_change=first_action_change,first_reference_physical_divergence_s=physical_divergence,whole_pending_plan_change_is_not_immediate_action_change=True))
 save(STUDY/'FIRST_SEGMENT_PAIR_VERIFICATION.json',dict(status='PASS' if checks and all(r['pass_'] for r in checks) else 'FAIL' if checks else 'PENDING',pairs=len(checks),rows=checks));save(STUDY/'PHYSICAL_DIVERGENCE.json',dict(rows=divergences));print(json.dumps(dict(first_segment_pairs=len(checks),all_pass=all(r['pass_'] for r in checks))))
if __name__=='__main__':main()
