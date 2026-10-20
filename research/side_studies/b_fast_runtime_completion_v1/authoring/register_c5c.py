from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/087_N13_S2_C5b_science_nominal.json').read_text());configs=[]
for n,kind in [(94,'science_nominal'),(95,'host_nominal'),(96,'science_deviation'),(97,'host_deviation')]:
 science=kind.startswith('science');legal='deviation' in kind;ident=f'{n:03d}_N13_S2_D2_C5c_{kind}'
 cfg=base|dict(id=ident,seed=2026100700+n,fast_version='N13_N12_N11_V3_W1_A1_D2_C1d_C2b_S2_C5c',committed_endpoint_service=True,committed_endpoint_precatch=False,committed_hold_continuous_precatch=True,execution_mode='SCIENTIFIC_SIMULATION' if science else 'REALTIME_CHARACTERIZATION',prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]} if legal else {},dependencies=['091_N13_S2_D2_science_nominal'],required_gates=['output/C5c_CONTINUOUS_COMMITTED_HOLD_REGRESSION.json','output/D2_TRANSPORT_WARM_LOCAL_REGRESSION.json'])
 if not science:
  sid='096_N13_S2_D2_C5c_science_deviation' if legal else '094_N13_S2_D2_C5c_science_nominal';cfg['required_gates'].append('versions/'+sid+'_SCI_GATE.json');cfg['dependencies']=[sid]
 p=S/'queue'/(ident+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');configs.append(str(p))
out=dict(id='C5c_CONTINUOUS_COMMITTED_HOLD_PRECATCH',registered_unix=time.time(),configs=configs,physics_budget=120,thresholds_unchanged=True,basis='088 C5b pre-catch begins after the first endpoint (lateby4.10ms); second crosses next regular deadline. Last-tick-only pre-catch is too late to keep the committed HOLD physics close to actual host time.',intervention='Before every timer while an original .5s HOLD remains committed, integrate only real elapsed old-command intervals with original .25ms events, then use the original timer or endpoint opportunity. No future-state projection or command/dwell/time-limit change.',independent_engineering_measurement=True,no_Q_or_training=True,other_unstarted_legal_versions_preserved='083/084 and089/090 remain unstarted diagnostic queues superseded by specific measured timing refinement.',H1_closed='184 exact statics hits,480 controller array comparisons; median gain46.894us is small, no physical candidate installation.')
p=S/'versions/C5c_PROSPECTIVE_PROTOCOL.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print('C5c_REGISTERED',len(configs))
