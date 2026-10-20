from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/062_N13_S2_science_nominal.json').read_text());cfgs=[]
for n,kind in [(77,'science_nominal'),(78,'host_nominal'),(79,'host_deviation'),(80,'science_deviation')]:
 legal='deviation' in kind;science=kind.startswith('science');ident=f'{n:03d}_N13_S2_C4_{kind}'
 cfg=base|dict(id=ident,seed=2026100700+n,fast_version='N13_N12_N11_V3_W1_A1_D1_C1d_C2b_S2_C4',readiness_service=True,completed_result_service=False,completed_result_precatch=False,execution_mode='SCIENTIFIC_SIMULATION' if science else 'REALTIME_CHARACTERIZATION',prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]} if legal else {},dependencies=['062_N13_S2_science_nominal'],required_gates=['output/C4_READINESS_SERVICE_LOCAL_REGRESSION.json'])
 if not science:
  sid='080_N13_S2_C4_science_deviation' if legal else '077_N13_S2_C4_science_nominal';cfg['dependencies']=[sid];cfg['required_gates'].append('versions/'+sid+'_SCI_GATE.json')
 path=S/'queue'/(ident+'.json')
 assert ident not in json.loads((S/'TASK_LEDGER.json').read_text())
 if path.exists():assert json.loads(path.read_text())==cfg
 else:path.write_text(json.dumps(cfg,indent=2)+'\n')
 cfgs.append(str(path))
out=dict(id='C4_PROSPECTIVE_TIMER_OR_TASK_READINESS_COMPLETE',registered_unix=time.time(),configs=cfgs,checks=str(S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json'),checks_unchanged=True,service_population='Every actual service including socket-woken opportunities; original same 5ms grid and missed-grid accounting, no synthetic callback.',hypothesis='Observed HOLD result completion-to-collection delay up to5.23ms; existing bounded timer sleep can end at actual original TASK packet readiness. Reduce main scheduling latency while retaining original current validation and causal writes.',authority='No future request, no forward phase projection, no new reference, no expiry or task tolerance change. Existing old-command physics catch-up before bounded sleeping.',physics_budget_current=120,no_Q_or_training=True,closed_loop_qualification_pending=True,registration_repair='First script placed protocol write inside loop; preserved partial registration, no physical dispatch occurred. Existing two configs validated byte-equivalent data, remaining two added; this complete protocol freezes all four before dispatch.')
path=S/'versions/C4_PROSPECTIVE_PROTOCOL_COMPLETE.json';assert not path.exists();path.write_text(json.dumps(out,indent=2)+'\n');print('C4_REGISTERED',len(cfgs))
