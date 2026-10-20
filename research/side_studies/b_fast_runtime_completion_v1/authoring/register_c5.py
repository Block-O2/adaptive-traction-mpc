from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/062_N13_S2_science_nominal.json').read_text());configs=[]
for n,kind in [(81,'science_nominal'),(82,'host_nominal'),(83,'science_deviation'),(84,'host_deviation')]:
 science=kind.startswith('science');legal='deviation' in kind;ident=f'{n:03d}_N13_S2_C5_{kind}'
 cfg=base|dict(id=ident,seed=2026100700+n,fast_version='N13_N12_N11_V3_W1_A1_D1_C1d_C2b_S2_C5',committed_endpoint_service=True,readiness_service=False,completed_result_service=False,execution_mode='SCIENTIFIC_SIMULATION' if science else 'REALTIME_CHARACTERIZATION',prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]} if legal else {},dependencies=['062_N13_S2_science_nominal'],required_gates=['output/C5_COMMITTED_ENDPOINT_LOCAL_REGRESSION.json'])
 if not science:
  sid='083_N13_S2_C5_science_deviation' if legal else '081_N13_S2_C5_science_nominal';cfg['dependencies']=[sid];cfg['required_gates'].append('versions/'+sid+'_SCI_GATE.json')
 path=S/'queue'/(ident+'.json');assert not path.exists();path.write_text(json.dumps(cfg,indent=2)+'\n');configs.append(str(path))
out=dict(id='C5_COMMITTED_HOLD_ENDPOINT_ACTUAL_SERVICE',registered_unix=time.time(),configs=configs,thresholds_unchanged=True,service_population='All original and additional real services; same frozen missed-grid/backlog checks; no past callbacks.',basis='C4 reduced no HOLD collection waits. Observed first segment end to second request plus final endpoint to phase check adds approximately12ms of actual service quantization.',scope='Only already activated nonrolling original .5s HOLD plans; original actual_activation_hook runs first. Register current native step+2000 as a timer opportunity. Original completion, sensor dwell, current safety, planner requests, and .5s duration remain unchanged.',no_pre_activation_dwell_credit=True,no_new_planner_authority=True,no_Q_or_training=True,local_clock_long_time_negative='At10000s iterativefloat original completion may be delayed; C5 neither changes nor bypasses this test, and is not a long-time integer-clock repair.',physics_budget=120)
p=S/'versions/C5_PROSPECTIVE_PROTOCOL.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print('C5_REGISTERED',len(configs))
