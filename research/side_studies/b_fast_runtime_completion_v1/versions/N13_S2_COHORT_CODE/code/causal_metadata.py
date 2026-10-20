"""C1c metadata: retain actual model/reference/write provenance per receipt.

No reference, physical state, source timestamp or lifecycle event is changed.
Offline support is observed before the active epoch, never restamped as new.
"""
import time,hashlib,pickle,struct
INSTALLED=False
def digest(parts):
 encoded=[]
 for value in parts:
  data=value.tobytes() if hasattr(value,'tobytes') else str(value).encode()
  tag=(str(value.dtype)+str(value.shape)).encode() if hasattr(value,'tobytes') else type(value).__name__.encode()
  encoded.extend((struct.pack('!Q',len(tag)),tag,struct.pack('!Q',len(data)),data))
 return hashlib.sha256(b''.join(encoded)).hexdigest()
def enrich(self,receipt):
 receipt['runtime_model_sequence']=receipt.get('model_version')
 receipt['model_version']=receipt.get('validation_model_version')
 receipt['model_version_authority']='original command validation_model_version'
 if receipt.get('apply_ns') is not None:
  receipt['actual_written_source_age_ns']=receipt['apply_ns']-receipt['source_capture_ns']
 receipt['reference_version_schema']='C1c committed Human reference + actual TRACK robot pose/twist, or selected executable BRAKE command'
 parts=[receipt.get('validation_reference_q_rad'),receipt.get('validation_reference_dq_rad_s'),receipt.get('model_version'),receipt.get('supervisor_mode')]
 if receipt.get('applied') and receipt.get('supervisor_mode')=='TRACK':
  emitted=self.runtime.get('emitted_robot_reference_history',[])
  if emitted and emitted[-1].get('apply_ns')==receipt.get('apply_ns'):
   item=emitted[-1];pose=item['pose'];receipt.update(actual_robot_reference_rotation=pose.rotation.copy(),actual_robot_reference_translation=pose.translation.copy(),actual_robot_reference_twist=item['twist'].copy())
   parts.extend((pose.rotation,pose.translation,item['twist']))
   receipt['actual_reference_kind']='COMMITTED_TRACK_REFERENCE'
 else:
  parts.extend((receipt.get('command_torque_nm'),receipt.get('selected_command_force_total_n'),receipt.get('selected_command_moment_total_nm')))
  receipt['actual_reference_kind']='SELECTED_EXECUTABLE_COMMAND'
 receipt['reference_version']=digest(parts)
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp,fast_plant as fp
 original_write=fp.CachedStage5CR12SensorBoundaryPlant.apply_executable_command
 def write(self,command):
  result=original_write(self,command);self._fast_observed_actuator_write_ns=time.monotonic_ns();return result
 fp.CachedStage5CR12SensorBoundaryPlant.apply_executable_command=write
 original_init=wp.WallPhysicsSession.__init__
 def init(self,*args,**kw):
  original_init(self,*args,**kw)
  if self.applied_commands and self.applied_commands[0].get('origin')=='offline validated support continuing into active epoch':
   receipt=self.applied_commands[0];receipt['offline_actual_write_ns']=getattr(self.plant,'_fast_observed_actuator_write_ns',None)
   receipt['offline_support_model_sha256']=hashlib.sha256(pickle.dumps(self.runtime.get('model'),protocol=5)).hexdigest()
   receipt['offline_support_command_sha256']=digest((receipt['command_torque_nm'],))
   receipt['write_observation_scope']='actual actuator write before active epoch; original source setup and apply_ns=None retained'
 original_apply=wp.WallPhysicsSession.apply
 def apply(self,*args,**kw):
  try:
   receipt=original_apply(self,*args,**kw);enrich(self,receipt);return receipt
  except BaseException as error:
   receipt=getattr(error,'applied_receipt',None)
   if receipt is not None:enrich(self,receipt)
   raise
 wp.WallPhysicsSession.__init__=init;wp.WallPhysicsSession.apply=apply;INSTALLED=True
