"""Write END last, only after the exact packet verifier process and tool exit."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]


def sha(rel):
    return hashlib.sha256((P / rel).read_bytes()).hexdigest()


def read(rel):
    return json.loads((P / rel).read_text())


def save(rel, value):
    with (P / rel).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def identity(pid):
    try:
        return dict(pid=pid, start_ticks=int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]))
    except FileNotFoundError:
        return None


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--expected-packet-sha256', required=True)
    cli.add_argument('--observed-verifier-tool-exit-code', required=True, type=int)
    cli.add_argument('--observed-verifier-tool-session-id', required=True, type=int)
    args = cli.parse_args()
    assert time.time() + 10 < 1793114740.0
    assert args.observed_verifier_tool_exit_code == 0
    assert args.observed_verifier_tool_session_id > 0
    assert sha('PACKAGE_VERIFICATION.json') == args.expected_packet_sha256
    packet = read('PACKAGE_VERIFICATION.json')
    assert packet['status'] == 'PASS_FOR_RECORDED_RESEARCH_SCOPE'
    owner = packet['finite_packaging_process']
    now_owner = identity(owner['pid'])
    assert now_owner is None or now_owner['start_ticks'] != owner['start_ticks'], 'PACKET_VERIFIER_STILL_ALIVE'
    assert sha(packet['full_packet_manifest']['path']) == packet['full_packet_manifest']['sha256']
    for rel, expected in packet['required_deliverables'].items():
        assert sha(rel) == expected['sha256'], rel
    assert 'Exit status: 0' in (P / 'audit/FINAL_PACKET_EXTERNAL_RESOURCE_V1.txt').read_text()
    assert read('WORK_STATE.json')['status'] == 'STOP'
    assert not (P / 'END.json').exists()
    writer = identity(os.getpid())
    joined = dict(schema='v8.final_packet_original_tool_join.v1', status='VERIFIER_EXIT0_ORIGINAL_IDENTITY_GONE',
                  created_unix=time.time(), verifier_original_identity=owner, verifier_current_PID_observation=now_owner,
                  observed_tool_exit_code=0, observed_tool_session_id=args.observed_verifier_tool_session_id,
                  tool_observation_scope='Root supplies the actually collected matching verifier session; this script does not self-authenticate tool service observations.',
                  packet_sha256=args.expected_packet_sha256,
                  external_resource=dict(path='audit/FINAL_PACKET_EXTERNAL_RESOURCE_V1.txt', sha256=sha('audit/FINAL_PACKET_EXTERNAL_RESOURCE_V1.txt')),
                  finite_END_writer_identity=writer,
                  scope='Current finite metadata writer is joined by root before the final reply; no scientific process starts here.')
    save('audit/FINAL_PACKET_TOOL_JOIN_V1.json', joined)
    ended = time.time()
    assert ended < 1793114740.0
    end = dict(schema='v8.final_research_END.v1', status='STOP', research_scope_status='COMPLETED_WITH_SCOPED_INCONCLUSIVE_METHOD_FAMILY_RESULTS',
               activation=read('ACTIVATION.json')['activation_id'], T0_unix=1793071540.0,
               original_global_stop_unix=1793114740.0, ended_unix=ended,
               elapsed_wall_since_T0_s=ended-1793071540.0, clock_reset=False,
               package_verification=dict(path='PACKAGE_VERIFICATION.json', sha256=args.expected_packet_sha256, status=packet['status']),
               packet_tool_join=dict(path='audit/FINAL_PACKET_TOOL_JOIN_V1.json', sha256=sha('audit/FINAL_PACKET_TOOL_JOIN_V1.json')),
               actual_physical_START=packet['exact_physical_ids'], actual_physical_END=packet['exact_physical_ids'],
               actual_new_native_steps=packet['exact_new_native_steps'],
               original_new_parameter_condition_count=2,
               historical_content_protection='PASS', original_journal_prefix_preserved=True,
               original_model_source_pins='PASS', evaluator_coverage=packet['coverage'],
               owned_research_scope='All registered experimental supervisors/known helper identities closed at final owned audit; package command scan clear; verifier tool exit0 and original identity gone. Missing old tick metadata retained UNKNOWN.',
               finite_END_writer_identity=writer,
               all_five_method_families='NOT_FULLY_EXPLORED', strong_baseline_independent_increment='NOT_ESTABLISHED',
               net_physical_or_compute_efficiency='NOT_ESTABLISHED', global_CPU_GPU_peak_RSS='UNKNOWN_NOT_IMPUTED_ZERO',
               Beta_second_batch='EXTERNAL_PENDING_9_DRAWS_THREE_PARENT_HARD_SCOPES_UNKNOWN_NO_CANCEL_NO_SECOND_COMMIT',
               unauthorized_history_mutation_Git_writes_Stage2_hardware_or_server_expansion=False,
               next_research_auto_start=False, new_model_scorer_fit_RNG_physics_from_END_writer=0,
               finalization_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save('END.json', end)
    print(json.dumps(dict(status=end['status'], ended_unix=ended, END_sha256=sha('END.json'), finite_writer=writer)))


if __name__ == '__main__':
    main()
