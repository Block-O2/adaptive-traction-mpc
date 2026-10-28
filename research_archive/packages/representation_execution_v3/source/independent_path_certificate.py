"""Independent 70-digit divided-difference necessary-condition check; no scipy fitter."""
from pathlib import Path
from decimal import Decimal,localcontext
import json,math,itertools
P=Path(__file__).resolve().parents[1];O=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2');su=json.loads((O/'runtime/source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json').read_text());case=json.loads((O/'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text());start=list(map(math.radians,case['task']['start_deg']));span=[math.radians(g)-s for g,s in zip(case['task']['goal_deg'],start)];slots=[];rejectmargins=[]
for lr in su['learning_records'][1:5]:
 ds=[]
 for c in lr['candidate_set']:
  if not c['label'].startswith('outbound_dq_'):continue
  q=c['target_q_rad'];target=lr['selected_plan']['target_q_rad'];m=sum((a-b)/sp for a,b,sp in zip(q,start,span))/2;u=2*m-1;e=math.sin(math.pi*min(1,max(0,m)))**2;sh=[(a-b)/sp for a,b,sp in zip(target,q,span)];cc=(sh[0]+sh[1])/2;dd=(sh[0]-sh[1])/2
  # Box envelope in normalized progress for arbitrary six old path coefficients.
  bound=e*(.015*(1+abs(u)+u*u)+.025*(1+abs(u)+u*u));excess=max(abs(v)-bound for v in sh)
  if excess>1e-12:rejectmargins.append(excess);continue
  ds.append({'label':c['label'],'u':u,'e':e,'c':cc,'d':dd})
 slots.append(ds)
checks=[]
with localcontext() as ctx:
 ctx.prec=70
 for combo in itertools.product(*slots):
  us=[Decimal(str(x['u'])) for x in combo];ee=[Decimal(str(x['e'])) for x in combo];vals={}
  for mode in ['c','d']:
   total=Decimal(0)
   for i,row in enumerate(combo):
    den=ee[i]
    for j,u in enumerate(us):
     if i!=j:den*=us[i]-u
    total+=Decimal(str(row[mode]))/den
   vals[mode]=str(total)
  checks.append({'labels':[c['label'] for c in combo],'third_divided_differences':vals,'must_both_equal_zero_for_quadratic':True})
out={'status':'INCOMPATIBLE_STATIC_QUADRATIC_AT_RECORDED_REQUESTS' if all(abs(Decimal(c['third_divided_differences']['c']))>Decimal('1e-10') or abs(Decimal(c['third_divided_differences']['d']))>Decimal('1e-10') for c in checks) else 'REVIEW','surviving_candidates_per_slot':[len(s) for s in slots],'surviving_combinations':len(checks),'min_rejected_grid_normalized_shift_excess':min(rejectmargins),'checks':checks,'precision_digits':70,'basis_sin_values':'Independent Python math.sin evaluated at registered task progress; polynomial consistency recomputed in Decimal70. Numerical implementation certificate, not arbitrary controller-family theorem.'};(P/'analysis/INDEPENDENT_PATH_CERTIFICATE.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
