"""Pure offline consistency checks for retained P05/P06 evidence and v3 figures."""
import json,hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);checks=[]
def record(name,cond):
 assert cond,name
 checks.append(name)
d=json.loads((p/'audit_human/P05_FAILURE_DETAILS_INITIAL.json').read_text());rows={r['patient_id']:r for r in d['patients']};x=rows['P05']
failed=[(r['signal'],r['statistic'],r['joint']) for r in x['per_joint_burden_gates'] if r['failed']]
record('P05 only two failed burden entries are knee speed max and knee acceleration p95',failed==[('velocity_deg_s','max_abs','knee'),('acceleration_deg_s2','p95_abs','knee')])
record('P05 only knee excursion fails',[r['joint'] for r in x['excursion_gates'] if r['failed']]==['knee'])
for r in x['per_joint_burden_gates']:
 record('burden arithmetic '+r['signal']+'/'+r['statistic']+'/'+r['joint'],abs(r['ratio']-r['H150']/r['B'])<1e-12 and r['failed']==(r['H150']>r['threshold']+1e-7))
e=json.loads((p/'audit_human/MECHANISM_EVIDENCE_THROUGH_P05.json').read_text());rr={r['patient_id']:r for r in e['patients']}
for pid,expected in [('P00',.47424712381670986),('P05',.7129890062696944)]:
 a=rr[pid]['arms'];under=a['H150']['motion_extra']['return_undershoot_deg'][1]-a['B']['motion_extra']['return_undershoot_deg'][1];over=a['H150']['motion_extra']['outbound_overshoot_deg'][1]-a['B']['motion_extra']['outbound_overshoot_deg'][1]
 record(pid+' knee full-excursion decomposition',abs(under+over-expected)<1e-10)
record('P05 H absolute knee undershoot is below P00 H',rr['P05']['arms']['H150']['motion_extra']['return_undershoot_deg'][1]<rr['P00']['arms']['H150']['motion_extra']['return_undershoot_deg'][1])
e6=json.loads((p/'audit_human/P06_FAILURE_DETAILS.json').read_text());req=e6['failed_requests']
record('P06 joined before extraction',e6['done']['all_children_joined'] and e6['owner']['joined'])
record('P06 gain unavailable',not e6['full_integral_comparison_valid'] and e6['gain_percent'] is None and e6['H150']['J_F_N_s'] is None)
record('P06 first failed request has nonzero reference knee velocity',req[0]['request']['request_id']==19 and not req[0]['recorded_start_knee_velocity_conjunct_pass'])
record('P06 second failed request has zero reference knee velocity',req[1]['request']['request_id']==20 and req[1]['recorded_start_knee_velocity_conjunct_pass'])
record('P06 no terminal H150 activated',e6['H150']['interventions']['counts']['H150']==0)
s=p/'audit_figures/v3_P05_failure';manifest=json.loads((s/'FIGURE_MANIFEST.json').read_text())
record('v3 six complete valid pairs and five fully qualified',manifest['complete_valid_pair_count']==6 and manifest['fully_qualified_h150_count']==5)
record('v3 manifest pinned',hashlib.sha256((s/'FIGURE_MANIFEST.json').read_bytes()).hexdigest()=='49f29acc04546e85fe64e769ca70650c3f9a049c314635681c272c60cd432054')
for f in manifest['figures']:record('v3 image '+f['file'],hashlib.sha256((s/'images'/f['file']).read_bytes()).hexdigest()==f['sha256'])
t=next(f for f in manifest['figures'] if f['file']=='06_terminal_timeline.png');record('timeline first failure P05',t['selected_patient']=='P05')
out={'status':'PASS','checks':checks,'check_count':len(checks),'physics_starts':0,'scope':'Offline evidence arithmetic and immutable v3 image hashes; no claim that P05/P06 scientific qualification passed.'}
(p/'audit_human/FAILURE_EVIDENCE_NUMERICAL_QA.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='checks'}))
