from pathlib import Path
import json,time,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/095_N13_S2_D2_C5c_host_nominal.json').read_text())
shutil.copy2(S/'code/committed_endpoint_service.py',S/'versions/C5c_COMMITTED_ENDPOINT_SERVICE.py')
configs=[]
for n,kind in [(98,'science_nominal'),(99,'host_nominal'),(100,'science_deviation'),(101,'host_deviation')]:
 science=kind.startswith('science');legal='deviation' in kind;ident=f'{n:03d}_N13_S2_D2_C6_{kind}'
 cfg=base|dict(id=ident,seed=2026100700+n,fast_version='N13_N12_N11_V3_W1_A1_D2_C1d_C2b_S2_C6',committed_endpoint_service=True,committed_endpoint_precatch=False,committed_hold_continuous_precatch=False,readiness_service=True,compose_readiness_and_endpoint=True,execution_mode='SCIENTIFIC_SIMULATION' if science else 'REALTIME_CHARACTERIZATION',prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]} if legal else {},dependencies=['094_N13_S2_D2_C5c_science_nominal'],required_gates=['output/C4_READINESS_SERVICE_LOCAL_REGRESSION.json','output/C5_COMMITTED_ENDPOINT_LOCAL_REGRESSION.json','output/D2_TRANSPORT_WARM_LOCAL_REGRESSION.json','output/C6_COMPOSITION_LOCAL_REGRESSION.json'])
 if not science:
  sid='100_N13_S2_D2_C6_science_deviation' if legal else '098_N13_S2_D2_C6_science_nominal';cfg['dependencies']=[sid];cfg['required_gates'].append('versions/'+sid+'_SCI_GATE.json')
 p=S/'queue'/(ident+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');configs.append(str(p))
 p=None
out=dict(id='C6_COMPOSE_ORIGINAL_COMPLETION_AND_COMMITTED_ENDPOINT',registered_unix=time.time(),configs=configs,basis='095 HOLD request12 completion-to-collection4.909838ms, request13.936971ms. C5c continuous pre-catch failed HOLD1.035 and is closed. C4 bounded socket-readiness can address completed-result collection, while C5a endpoint opportunity covers committed-duration completion; distinct actual timer cases can be composed.',ordering='C5 endpoint outer wrapper delegates ordinary waits to original C4 bounded readiness wrapper then C2; no continuous pre-catch. No extra request/dwell credit/reference authority, unchanged all actual service population.',thresholds_unchanged=True,Q=False,physics_budget=120,unstarted_C5c_legal='096/097 not dispatched because nominal mechanism showed no gain; preserved unused queue.')
(S/'versions/C6_PROSPECTIVE_PROTOCOL.json').write_text(json.dumps(out,indent=2)+'\n');print('C6_REGISTERED')
