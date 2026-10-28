from pathlib import Path
import json,shutil,time,hashlib,difflib
S=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
p=S/'code/host_adapter.py';before=p.read_text();after=(W/'host_adapter.py').read_text();assert after==before.replace('source_inputs=hint,','source_inputs=sc.clean(hint),')
shutil.copy2(p,S/'versions/host_adapter_v2_export_failed.py');p.write_text(after)
(S/'reports/EVIDENCE_SERIALIZATION_REPAIR.json').write_text(json.dumps(dict(unix=time.time(),failed_attempt='005_M2_guard_off_retry',error='PlanRequest dataclass in evidence source_inputs not supported by unchanged native summary JSON exporter',change='Materialize evidence-only source inputs with existing sc.clean before returning metadata; no selection/mask/admission/guard/control/safety change',before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest(),native_physics_failure=False,failed_export_not_promoted_to_valid_task=True,selection_adapter_additional_repair_cycles=0),indent=2))
cfg=json.loads((S/'queue/005_M2_guard_off_retry.json').read_text());cfg.update(id='017_M2_guard_off_export_retry',adapter_version='M2_C13_ENVELOPE_v2_JSON_EVIDENCE')
(S/'queue'/(cfg['id']+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
print('Evidence-only dataclass serialization fixed; native selection and admission unchanged')
