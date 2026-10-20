from pathlib import Path
import json,time,shutil,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1');V=P/'versions/interface1';V.mkdir(parents=True,exist_ok=False)
assert json.loads((P/'control/OWNER_interface1.json').read_text())['joined']
for d in ['control','tests','source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1']:
 dest=V/d;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(P/d,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for n in ['EXECUTION_CODE_MANIFEST.json','PHYSICAL_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json','MATH_VALIDATION.json','P0_ZERO_PHYSICAL_GATE.json','PARENT_FORK_GATE.json','PHYSICAL_ARM_RESULTS.json','PHYSICAL_PROGRESS.json','PHYSICAL_DONE.json']:
 if (P/n).exists():shutil.copy2(P/n,V/n)
issue=dict(discovered_unix=time.time(),status='LOGGING_ONLY_REPAIR',old_group='interface1',actual_sampling_and_certification_duration_correct=True,problem='FrozenPolynomial.record flattened original whole-segment metadata, so displayed child durations were 1.27 instead of actual .3175; true coefficients, knots, actual instance duration, certificate and sample correct',preserved_source=str(V),repair='record actual child time and boundaries; add complete identity payload for independent hash reconstruction; no controller or safety changes',new_physics='interface2: matched B0, zero multi, prior motion-qualified +.02deg, one identical matched repeat. No .05 retry or force selection',budget='5 previous STARTs + 5 final STARTs = 10 <=24')
(P/'audit/SERIALIZATION_REPAIR.json').write_text(json.dumps(issue,indent=2))
f=P/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py';s=f.read_text();old="    def record(self):return {**json.loads(self.metadata_json),'immutable_coefficients':self.values}"
new='''    def record(self):
        first,last=self.sample(0.),self.sample(self.duration_s)
        return dict(version=self.version,reference_period_s=self.reference_period_s,
            duration_s=self.duration_s,immutable_coefficients=self.values,
            start_q_rad=first.q_rad,start_dq_rad_s=first.dq_rad_s,start_ddq_rad_s2=first.ddq_rad_s2,
            target_q_rad=last.q_rad,target_dq_rad_s=last.dq_rad_s,target_ddq_rad_s2=last.ddq_rad_s2,
            maximum_reference_velocity_rad_s=self.maximum_reference_velocity_rad_s,
            maximum_reference_acceleration_rad_s2=self.maximum_reference_acceleration_rad_s2,
            original_source_metadata=json.loads(self.metadata_json))'''
assert old in s;s=s.replace(old,new).replace('safe_escape_identity=digest(self.safe_escape))','safe_escape_identity=digest(self.safe_escape),identity_payload=primitive(self.content()))');f.write_text(s)
f=P/'control/physical_runner.py';s=f.read_text();start=s.index("   rows=[('B0'");end=s.index("   put('PHYSICAL_ARM_RESULTS",start)
s=s[:start]+'''   rows=[('B0','B',0.),('zero_multi','ZERO',0.),('knee_002','NONZERO',.02),('knee_002_repeat','NONZERO',.02)]
   for tag,kind,amplitude in rows:
    if self.eval_arm(b,tag,kind,amplitude):return self.control(b)
    if tag=='zero_multi':
     gate=compare_raw(GROUP+'_B0',GROUP+'_zero_multi',allow_reference_identity=True);put('P0_ZERO_PHYSICAL_GATE.json',gate);assert gate['status']=='PASS','P0_ZERO_PHYSICAL_DIFFERENCE'
    if tag=='knee_002':assert self.metrics[-1]['motion']['acceptance_pass'],'FINAL_DEMO_MOTION_FAILURE'
    if tag=='knee_002_repeat':
     repeat=compare_raw(GROUP+'_knee_002',GROUP+'_knee_002_repeat',allow_reference_identity=True);put('NONZERO_REPEAT_GATE.json',repeat);assert repeat['status']=='PASS','NONZERO_REPEAT_DIFFERENCE'
''' + s[end:];f.write_text(s)
f=P/'tests/test_certification.py';s=f.read_text();pos=s.index('output=dict(status=');s=s[:pos]+'''def serialized_piece_times_and_identity():
 for obj in [zero,nonzero]:
  r=primitive(obj.record());assert digest(r['identity_payload'])==r['reference_id']
  assert digest([r['reference_id'],encode(r['path_certificate'])])==r['certificate_id']
  assert abs(sum(x['duration_s'] for x in r['segments'])-r['duration_s'])<1e-12
  for i,row in enumerate(r['segments']):
   assert abs(row['duration_s']-(r['knots_s'][i+1]-r['knots_s'][i]))<1e-12
   p=obj.segments[i]
   assert np.array_equal(row['start_q_rad'],p.sample(0.).q_rad)
   assert np.array_equal(row['target_ddq_rad_s2'],p.sample(p.duration_s).ddq_rad_s2)
 return dict(local_durations_accurate=True,complete_identity_reconstructed=True)
test('serialization_actual_piece_times_boundaries_and_complete_identity',serialized_piece_times_and_identity)
''' + s[pos:];f.write_text(s)
print('preserved interface1, repaired summary only, registered interface2 .02 repeat')
