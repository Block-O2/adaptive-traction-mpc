from pathlib import Path
import json,hashlib
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/L.name;A=S/'m2_18d_terminal_response_repair_v1';out=[]
root='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/'
for n,needle,radius in [(root+'scientific_scheduler.py','STALE_SIMULATED_SOURCE_MAXIMUM_AGE',7),(root+'runtime_coordination_residual_v2.py','ACTUAL_REMAINING_PHASE_TIME',6),(root+'runtime_coordination_residual_v2.py','runtime["plan_lifecycle"].activate',5)]:
 f=A/n;lines=f.read_text().splitlines()
 for i,line in enumerate(lines):
  if needle in line:out.append(dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),start_line=max(1,i-radius+1),text='\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-radius),min(len(lines),i+radius+1)))))
(P/'audit/T_TIME_SOURCE_SUPPLEMENT.json').write_text(json.dumps(dict(status='PASS',rules=out,scope='Read-only source evidence supplements initial contract gate; no changes to execution'),indent=2)+'\n')
print('SOURCE_SUPPLEMENT',len(out))
