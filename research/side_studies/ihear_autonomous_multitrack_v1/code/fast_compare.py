from pathlib import Path
import json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1')
rows=[]
for base,ids in ((S,[r['id'] for r in json.loads((S/'TASK_LEDGER.json').read_text()).values() if r.get('worker_status')=='COMPLETE']), (S.parent/'b_hold_return_critical_path_v1',['047_C13_host_nominal_quiet','048_C13_host_deviation_quiet']), (S.parent/'b_runtime_qualification_decoupling_v1',['002_B_confirm_deviation','003_B_confirm_nominal_harness_retry','004_B_quiet_retest_nominal','005_B_quiet_retest_deviation'])):
    for ident in ids:
        p=base/'output'/(ident+'_MULTIRATE.json')
        if not p.exists():continue
        e=json.loads(p.read_text());x=[(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in e['rows']['fast'] if r.get('service_finish_ns') is not None]
        phases={}
        for phase in ('TASK','COMMISSIONING','HOLD','OUTBOUND','RETURN'):
            y=[(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in e['rows']['fast'] if r.get('service_finish_ns') is not None and (r.get('stage')==phase or r.get('phase')==phase)]
            if y:phases[phase]=dict(n=len(y),p95=float(np.percentile(y,95)),max=float(max(y)))
        functional=base/'reports'/(ident+'_FUNCTIONAL.json')
        f=json.loads(functional.read_text()) if functional.exists() else {}
        rows.append(dict(id=ident,path=str(p),n=len(x),service_wall_compute_ms=dict(p50=float(np.percentile(x,50)),p95=float(np.percentile(x,95)),p99=float(np.percentile(x,99)),max=float(max(x))),phase=phases,rolling_1s_ms=f.get('rolling_1s_mean_ms'),service_gap=f.get('service_gap_ms')))
out=dict(status='PASS',rows=rows,interpretation='Compare exact original service_start_ns to service_finish_ns. Historical global p95 service gaps were7.87-9.58ms; historical global p95 service compute6.60-7.57ms. A rolling1s miss alone does not prove broad historical slowdown reproduction. All local tail/miss failures retained; no formal runtime promotion.')
(S/'reports/FAST_SERVICE_RECURRENCE_COMPARISON.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
