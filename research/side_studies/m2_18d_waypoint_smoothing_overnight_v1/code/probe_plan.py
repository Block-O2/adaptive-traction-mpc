"""Register bounded post-R3 diagnostic probes without changing architecture."""
from pathlib import Path
import json,time
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_multirate_realtime_v1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1')
profiles=[dict(id='031_R3_science_profile',revision='R3',execution_mode='SCIENTIFIC_SIMULATION',seed=2026100621,host_series='profiled_auxiliary')]
legal=[dict(id=f'{i:03d}_R3_host_deviation{j}',revision='R3',execution_mode='REALTIME_CHARACTERIZATION',seed=2026100740+j,host_series='legal_deviation',prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]}) for j,i in enumerate((32,33),1)]
for n,rows in [('profile_spec.json',profiles),('host_R3_deviation.json',legal)]:
 assert not (S/n).exists();(S/n).write_text(json.dumps(rows,indent=2)+'\n')
src=(S/'code/campaign.py').read_text().replace("str(S/'code/run_one.py')","str(S/'code/profile_run.py')")
assert not (S/'code/profile_campaign.py').exists()
(S/'code/profile_campaign.py').write_text(src)
(S/'DIAGNOSTIC_PROBE_PLAN.json').write_text(json.dumps(dict(registered_unix=time.time(),revision='R3 unchanged',order='consecutive join, scientific profiling, two legal host deviation probes',profile=profiles,legal=legal,qualification_scope='Profiler excluded. Legal deviation is supplemental; 4 cold + 4 same-interpreter remain mandatory.',no_fourth_architecture=True,no_Q_G_learning=True),indent=2)+'\n')
print('Registered three diagnostic probes')
