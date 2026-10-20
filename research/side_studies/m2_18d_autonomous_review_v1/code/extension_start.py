from extension_common import *

def main():
    guard(900)
    assert not (EXT/'RUN_PLAN.json').exists(), 'ALREADY_STARTED'
    EXT.mkdir(exist_ok=True);WIN_EXT.mkdir(exist_ok=True)
    manifests=[FIRST_DELIVERY/'DELIVERY_MANIFEST.json',FIRST_DELIVERY/'DELIVERY_EXPORT_MANIFEST.json',FIRST_DELIVERY/'DELIVERY_VALIDATION.json']
    accepted=json.loads(manifests[-1].read_text());assert accepted['status']=='PASS' and accepted['final']
    checkpoint=dict(start_unix=time.time(),first_delivery_path=str(FIRST_DELIVERY),accepted_files={str(p):sha(p) for p in FIRST_DELIVERY.rglob('*') if p.is_file()},attempts_sha256=sha(STUDY/'ATTEMPTS.jsonl'),physics_raw_summary_sha256=sha(STUDY/'reports/RAW_PHYSICS_PROVENANCE_AUDIT.json'),Q_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),original_closeout_sha256=sha(STUDY/'reports/CLOSEOUT_STATUS.json'))
    save(EXT/'BEFORE.json',checkpoint)
    plan=dict(status='ACTIVE_OFFLINE_DIAGNOSIS',start_unix=checkpoint['start_unix'],original_package_start_unix=START,deadline_unix=DEADLINE,deadline_local='2026-10-07 12:00 Asia/Shanghai',user_authorization='如果时间提前到了允许执行到12点整',time_cap_superseded=True,cumulative_physics_attempt_cap=160,attempts_used_at_extension=159,public_B_repairs_used=2,public_B_repair_cap=2,physics_dispatch_disabled=True,Q_updates=0,first_delivery_preserved=True,resource_cadence_s=45,heavy_dispatch_cutoff_unix=DEADLINE-2700,jobs=[dict(id='X01',script='extension_timer_service.py',scope='Saved-state B decision + a shadow 5ms timer. No plant/physics/activation. No promoted repair.'),dict(id='X02',script='extension_native_stage_profile.py',scope='Saved-state first/warm original B localization; no physics, no controller change.'),dict(id='X03',script='extension_backlog_audit.py',scope='Retained wall-clock prefix accounting, scheduler/receipt critical path and causal stage evidence.')],closeout='Independent extension preservation, hash/link validation, report. Keep original STOP_DISPATCH; never restart original runner.')
    save(EXT/'RUN_PLAN.json',plan)
    append('TASK_LEDGER.jsonl',dict(event='EXTENSION_START',unix=time.time(),physics_attempts_added=0,deadline_unix=DEADLINE))
    print(json.dumps(dict(status=plan['status'],deadline=plan['deadline_local'],accepted_delivery_files=len(checkpoint['accepted_files']),physics_dispatch_disabled=True)))

if __name__=='__main__':main()
