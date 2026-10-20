"""Offline gate coverage and XML robot actuator limit inspection; no physics."""
from pathlib import Path
import ast,json,hashlib,xml.etree.ElementTree as ET
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
def read(p):return json.loads(Path(p).read_text())
tree=ast.parse((P/'cross_analysis.py').read_text());constants={}
for node in tree.body:
    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ['TASK_KEYS','SAFETY_KEYS']:
        constants[node.targets[0].id]=ast.literal_eval(node.value)
matrix=P/'source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json'
measured=read(P/'reports/P00_H150_MEASURED.json')
evaluator=measured['native_physical_audit']['unchanged_evaluator']
common=evaluator['physical_task_result']['scorer_v2_common_conditions']
assigned=set(constants['TASK_KEYS'])|set(constants['SAFETY_KEYS'])|{'case_hash'}
unmapped=set(common)-assigned
xml=P/'patients/P00/static/model.xml';root=ET.parse(xml).getroot()
actuators=[dict(tag=x.tag,**x.attrib) for x in root.findall('./actuator/*')]
limits=[float(a['ctrlrange'].split()[1]) for a in actuators if 'ctrlrange' in a]
with np.load(P/'source/results/P00_H150/trace.npz') as z:
    ix=z['stage']=='TASK';tau=z['cr12_actuator_command_nm'][ix];peak=np.max(abs(tau),axis=0)
    fraction=float(np.max(peak/limits)) if len(limits)==len(peak) else None
data=dict(status='PASS' if not unmapped and set(common)==assigned else 'FAIL',
    scorer_common_conditions=common,task_keys=constants['TASK_KEYS'],absolute_safety_keys=constants['SAFETY_KEYS'],
    causal_case_hash=common.get('case_hash'),unmapped_conditions=sorted(unmapped),
    additional_gates=dict(finite_trace='absolute_safety',finite_native='absolute_safety',activation_certificates_valid='causal_execution',reference_boundary_C2='causal_execution',scientific_validity='causal_execution',online_certificates_valid='causal_execution',native_receipt_ownership='causal_execution'),
    excluded_plan_age='Only original scientific-mode semantics remove host wall plan_age; simulated source-version age under100ms remains in scientific_validity, receipt source age verified independently. Host realtime is unqualified.',
    contract=read(matrix)['scoring'],contract_sha256=hashlib.sha256(matrix.read_bytes()).hexdigest(),
    human_acceleration_semantics='Original absolute gate uses trace.actual_human_acceleration_rad_s2 only where actual_human_acceleration_valid; native0.25ms dq gradients are separately retained motion metrics, not substituted into this original gate.',
    raw_force_semantics='Original scorer uses summary TASK peak force/moment; native true_physics load monitor preserved separately.',
    actual_xml_sha256=hashlib.sha256(xml.read_bytes()).hexdigest(),robot_xml_actuators=actuators,
    robot_trace_task_peak_abs_nm=peak.tolist(),robot_xml_upper_ctrlrange_nm=limits,
    recomputed_trace_peak_torque_fraction=fraction,reported_peak_torque_fraction=evaluator['raw_scorer_v2']['peak_robot_torque_fraction'],
    caveat='Source gate coverage and P00 observed evidence; no new safety thresholds, no clinical claim, no full-native acceleration substitution.',new_physics_starts=0)
for p in [P/'audit/P00_ABSOLUTE_GATE_COVERAGE.json',R/'audit/P00_ABSOLUTE_GATE_COVERAGE.json']:
    assert not p.exists();p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(status=data['status'],unmapped=data['unmapped_conditions'],limits=limits,torque_fraction=fraction)))
