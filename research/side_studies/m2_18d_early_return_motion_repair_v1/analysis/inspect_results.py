from pathlib import Path
import json
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
out=[]
for r in json.loads((P/'EXPERIMENT_RESULTS.json').read_text())['rows']:
 m=r['complete_metrics'];f=m['motion']['raw']['full'];row=dict(id=r['id'],JF=r['J_F_N_s'],v95=f['velocity_deg_s']['p95_abs'],amax=f['acceleration_deg_s2']['max_abs'],a95=f['acceleration_deg_s2']['p95_abs'],jrms=f['jerk_deg_s3']['rms'],exc=m['dose']['excursion_deg'],tracking=m['tracking_RMS_deg'],moment=m['moment_integral_Nm_s'],force_peak=m.get('force_peak_N'),failed=r['motion']['failed_requirements'])
 if r['candidate'].get('early'):
  row.update(events=r['events'],actual_delta=r.get('actual_q_change_max_deg'),actual_dq_delta=r.get('actual_dq_change_max_deg_s'),first_actual_difference=r.get('first_actual_q_dq_difference_task_s'),pre_exact=r.get('pre_splice_q_dq_exact'),excursion_windows=r['excursion_failure_windows'],knee_burdens=[d for d in r['failure_window_diagnostics'] if d['joint']=='knee'])
 out.append(row)
(P/'derived/REPAIR_RESULT_INSPECTION.json').write_text(json.dumps(out,indent=2)+'\n')
short=[]
for row in out:
 s={k:v for k,v in row.items() if k not in ['events','knee_burdens']}
 if 'events' in row:s['RETURN_events']=[{k:e[k] for k in ['index','request','splice','duration']} for e in row['events'] if e['phase']=='RETURN']
 if 'knee_burdens' in row:s['knee_burdens']=[{**{k:v for k,v in b.items() if k!='intervals'},'longest_intervals':sorted(b['intervals'],key=lambda x:x['samples'],reverse=True)[:3]} for b in row['knee_burdens'] if b['signal']!='jerk_deg_s3']
 short.append(s)
print(json.dumps(short,indent=2),flush=True)
