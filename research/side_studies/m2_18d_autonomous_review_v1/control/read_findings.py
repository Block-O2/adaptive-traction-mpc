from pathlib import Path
import json
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
for label in ['historical_N2','N2']:
 f=P/'derived'/(label+'_MECHANISM.json');g=P/'derived'/(label+'_TRACKING_CHAIN.json')
 if not f.exists() or not g.exists():continue
 a=json.loads(f.read_text());b=json.loads(g.read_text())
 for arm,m in a['measures'].items():
  print(json.dumps(dict(label=label,arm=arm,JF=m['J_F_N_s'],peak=m['knee_peak'],knee_ratio=m['knee_acceleration_max_ratio_vs_B'],TV_v=m['actual_velocity_TV_deg_s'],TV_a=m['actual_acceleration_TV_deg_s2'],reference_acceleration_max=m['reference_max_abs_acceleration_deg_s2'],late_OUT_schedules=[r for r in b['schedules'][arm] if r['phase']=='OUTBOUND'][-3:]),ensure_ascii=False))
