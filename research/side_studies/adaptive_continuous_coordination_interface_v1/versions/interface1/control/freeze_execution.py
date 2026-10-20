from pathlib import Path
import json,hashlib,time,subprocess,ast
P=Path(__file__).resolve().parents[1]
rows=[]
for folder in ['code','source/stages','deps','native','build','weights','control','tests']:
 for f in sorted((P/folder).rglob('*')):
  if not f.is_file() or f.suffix=='.pyc' or '__pycache__' in str(f):continue
  if f.suffix=='.py':ast.parse(f.read_text())
  rows.append(dict(path=str(f.relative_to(P)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(frozen_unix=time.time(),files=rows,scope='physics sources including two isolated changes and new multisegment module; no production modifications'),indent=2))
protocol=dict(frozen_unix=time.time(),physics_budget=24,seed=2026101303,qualification_sequence=['matched parent','B0','zero multi P0 gate','single internal knee q perturbation +.05deg in second OUT request','one same-parent repeat if motion PASS'],target_outbound_request_index=1,perturbation=dict(joint='knee',internal_knot_fraction=.5,position_degrees=.05,velocity_change=0.,acceleration_change=0.,outer_endpoint_changes=0.,duration_changes=0.),bounded_reductions_only_for_motion_failure=[.02,.01],comparison='same complete live parent, original frozen task/safety/receipt/motion gates',P0='all physical trace/native/receipt numeric fields exact, identity fields explicitly audited',P1='actual multi payload activated and receipt samples from same certified identity, nonzero reference vs zero arm, applied torque/native ownership and actual Human response',P2='complete task and unchanged original absolute safety/motion/fairness',no_force_selection=True,no_cross_patient_or_unseen_claim=True)
(P/'PHYSICAL_PROTOCOL.json').write_text(json.dumps(protocol,indent=2))
print('FROZEN_EXECUTION',len(rows),'files',flush=True)
