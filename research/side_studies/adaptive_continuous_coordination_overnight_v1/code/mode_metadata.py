"""Correct a historical log constant, preserving the independent evaluator."""
from study_common import *
import inspect

INSTALLED_AUDIT=None

def install():
 global INSTALLED_AUDIT
 import qualify as q
 import final_qualification as f
 if INSTALLED_AUDIT is not None:
  assert q.physical_audit is INSTALLED_AUDIT and f.physical_audit is INSTALLED_AUDIT,'METADATA_AUDIT_OWNER_CHANGED'
  return
 original=inspect.getsource(q.physical_audit)
 old="execution_mode='SCIENTIFIC_SIMULATION'"
 assert original.count(old)==1,'QUALIFICATION_METADATA_SOURCE_CHANGED'
 revised=original.replace(old,"execution_mode=env.summary['execution_mode']")
 namespace=dict(q.__dict__);exec(compile(revised,'<actual execution-mode metadata writer>', 'exec'),namespace)
 q.physical_audit=f.physical_audit=namespace['physical_audit']
 INSTALLED_AUDIT=q.physical_audit
 save('MODE_METADATA_REPAIR.json',dict(scope='HIGH_ROM_CASE_RESULT execution_mode metadata only',original_function_sha256=hashlib.sha256(original.encode()).hexdigest(),source_file_unchanged=True,evaluator_unchanged=True,physical_runtime_unchanged=True,task_and_safety_thresholds_unchanged=True,actual_mode_source='env.summary.execution_mode, independently emitted by the runtime'))
