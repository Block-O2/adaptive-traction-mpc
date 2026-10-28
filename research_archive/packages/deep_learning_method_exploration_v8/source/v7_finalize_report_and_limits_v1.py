"""Finalize prose time scope and explicit limitations; do not change results."""
from pathlib import Path
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
O = P / 'audit/ROOT_TEXT_BEFORE_FINAL_STAMP'
assert not O.exists()
O.mkdir()
now = time.time()
a = json.loads((P / 'ACTIVATION.json').read_text())
elapsed = now - a['T0_unix']
hours, minutes = int(elapsed // 3600), int(elapsed % 3600 // 60)
rows = {}
for name in ['REPORT.md', 'BASELINE_AND_PAIRED_OPTIMIZATION.md']:
    f = P / name
    before = f.read_bytes()
    (O / name).write_bytes(before)
    s = before.decode()
    s = s.replace('analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V1.json', 'analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json')
    if name == 'REPORT.md':
        needle = '总研究/封包耗时：{{TOTAL_ELAPSED}}。'
        assert s.count(needle) == 1
        s = s.replace(needle, f'截至本报告定稿，研究已运行约{hours}小时{minutes}分；最终封包实际总耗时见END.json的elapsed_seconds。')
        needle = '这些不是170个独立患者或完整冷启动episode。'
        assert s.count(needle) == 1
        s = s.replace(needle, needle + '工程完整raw另列：DEVRC01_B的原物理资格已独立恢复PASS，但原worker工程失败和不排名保留；HOLDSS01_B属于HOLDSS02，缺原motion结论。DEVRT02_B在之后作业路径检查失败前已原合格，保持原资格，不把整作业判成功。')
    else:
        s += '\n\n**CONFIRMED（工程与科学结论分层）：** DEVRT02_B已完整原合格，之后历史路径检查失败不降级该B或改判整作业成功；DEVRC01_B原物理资格已恢复PASS，但原worker工程失败及不排名保留。HOLDSS01_B属于HOLDSS02且无原motion verdict，不补资格。完整身份见[协调V2](analysis/FINAL_EVIDENCE_CLASSIFICATION_RECONCILIATION_V2.json)。\n'
    f.write_text(s)
    rows[name] = {'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(f.read_bytes()).hexdigest()}

paths = [
    'agent_reviews/out0_context_scope/REPORT.md',
    'audit/HOLDSS02_LABEL_RECOVERY_REGISTRATION.json',
    'audit/FOREGROUND_METADATA_BUILDER_ERROR_20261026T2205.json',
    'agent_reviews/causal_stump_scope_v2b/REPORT.md',
    'agent_reviews/final_metadata_inventory/PREPARATION_AUDIT.json',
    'audit/review_closure_adapters_v1/ADAPTER_INDEX.json',
    'agent_reviews/causal_stumps_v1/deadline_repair_v2/END.json',
    'audit/OWNED_FINAL_V1.json',
]
evidence = {}
for rel in paths:
    f = P / rel
    assert f.is_file(), 'LIMITATION_EVIDENCE_MISSING:' + rel
    evidence[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
limits = {
    'status': 'DOCUMENTED_METADATA_LIMITATIONS_PRESENT', 'created_unix': now,
    'perfect_metadata_PASS_allowed': False,
    'foreground_static_tool_only_gap_present': True,
    'foreground_gap_scope': 'Plural foreground static/metadata commands retain tool exit receipts without complete original persisted PID/start_ticks; no retrospective identities fabricated.',
    'original_missing_END_reviews': ['history', 'local_surrogate'],
    'original_nonstandard_manifest_reviews': ['causal_human_interface', 'interface', 'terminal_rule'],
    'current_main_closure_adapters_not_original_ENDs': True,
    'zero_START_preimport_manifest_missing': ['DEVPC01', 'HOLDSS01'],
    'zero_START_complete_loaded_module_and_interpreter_identity_proven': False,
    'metadata_seal_budget_compliance_complete': False,
    'metadata_repair_registered_seconds': 600, 'metadata_repair_actual_seconds': 624.6121456623077,
    'metadata_repair_overrun_seconds': 24.61214566230774,
    'metadata_overrun_added_fit_env_physics': 0,
    'total_host_core_seconds_known': False,
    'full_historical_content_baseline_exact_T0': False,
    'historical_baseline_scope': 'Full hash captured approximately30min afterT0; original metadata/earlier critical checks and final fullhash retained. Never claimed exactT0 fullcontent.',
    'unrecorded_reparented_orphans_universally_proven_absent': False,
    'all_registered_scientific_physical_attempts_closed': True,
    'clinical_patients_or_hardware_validation': 0,
    'original_sources_raw_models_or_ENDs_reconstructed_to_hide_gaps': False,
    'evidence_sha256': evidence,
}
with (P / 'audit/FINAL_METADATA_LIMITATIONS_V1.json').open('x') as f:
    f.write(json.dumps(limits, ensure_ascii=False, indent=2) + '\n')
with (P / 'audit/FINAL_REPORT_STAMP_V1.json').open('x') as f:
    f.write(json.dumps({'status': 'FINAL_REPORT_PROSE_STAMPED_NO_RESULTS_CHANGED',
                        'process': {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])},
                        'report_asof_unix': now, 'report_asof_elapsed_seconds': elapsed,
                        'files': rows, 'all_old_text_preserved': str(O.relative_to(P)),
                        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, ensure_ascii=False, indent=2) + '\n')
print('REPORT_STAMPED', hours, minutes, 'minutes; limitations explicit')
