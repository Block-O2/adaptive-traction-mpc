"""主授权闭合元数据审查。仅stdlib；不导入候选/模型/scorer，不打开raw/trace。"""
import copy
import hashlib
import json
import os
import pathlib
import resource
import sys
import time

P = pathlib.Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT = pathlib.Path(__file__).parent
GROUP = 'V8POSTAPP02'
OLD = 'V8VAL04'
TAGS = ['B', 'LATE_H150_APPLICABILITY', 'EARLY_H150_APPLICABILITY', 'LATE_PHASE_APPLICABILITY', 'EARLY_PHASE_APPLICABILITY']
HARD = ['force', 'moment', 'torque', 'human_speed', 'human_acceleration', 'robot_speed', 'session_clearance', 'true_clearance', 'measured_sleeve_clearance', 'no_shank_table_contact', 'no_human_rom_violation']
refs = {}
checks = []
read_bytes = 0
t0, cpu0 = time.monotonic(), time.process_time()

def raw(rel):
    global read_bytes
    rel = str(pathlib.Path(rel).relative_to(P)) if pathlib.Path(rel).is_absolute() else str(rel)
    assert not rel.startswith('runtime/source/results/'), rel
    assert not rel.endswith(('.gz', '.npz')), rel
    b = (P / rel).read_bytes()
    read_bytes += len(b)
    refs[rel] = hashlib.sha256(b).hexdigest()
    return b

def read(rel):
    return json.loads(raw(rel))

def sha(rel):
    raw(rel)
    return refs[str(pathlib.Path(rel).relative_to(P)) if pathlib.Path(rel).is_absolute() else str(rel)]

def ck(name, value):
    checks.append({'check': name, 'PASS': value is True})

def tick(pid):
    try:
        return int(pathlib.Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None

def pin(ref, job):
    ck('pinned_ref:' + ref['path'], sha(ref['path']) == ref['sha256'] == job['files'].get(ref['path']))

def put(name, doc):
    path = OUT / name
    with path.open('x') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

gate_path = 'owned/RAW_REPLAY_1793111339297475644_END.json'
end_replay = read(gate_path)
ck('original_replay_closed_PASS6', end_replay['status'] == 'PASS' and end_replay['rows'] == 6 and end_replay['groups'] == [GROUP])
for tag in ['parent'] + TAGS:
    ck('original_replay_present:' + tag, (P / ('audit/scorer_replay/' + GROUP + '_' + tag + '.json')).is_file())
c = read('experiments/' + GROUP + '.json')
old = read('experiments/' + OLD + '.json')
job = read('jobs/' + GROUP + '/SOURCE_MANIFEST.json')
oldjob = read('jobs/' + OLD + '/SOURCE_MANIFEST.json')
sup = read('owned/' + GROUP + '_SUPERVISOR.json')
end = read('owned/' + GROUP + '_SUPERVISOR_END.json')
exit_doc = read('owned/' + GROUP + '_EXIT.json')
done = read('jobs/' + GROUP + '/WORKER_DONE.json')
ck('config_job_supervisor_identity', refs['experiments/' + GROUP + '.json'] == job['config_sha256'] == sup['config_sha256'])
ck('closed_owner_and_allchildren', end['state'] == 'STOP' and end['worker_exit_code'] == 0 and end['survivors'] == [] and exit_doc['active_child'] is None and done['all_children_joined'] is True and len(done['parent_checks']) == 5 and all(x['unchanged'] is True and x['child_exitcode'] == 0 for x in done['parent_checks']))
identities = list(end['known_owned'].values()) + [sup['identity'], sup['worker'], {'pid': end_replay['pid'], 'start_ticks': end_replay['start_ticks']}]
closed = []
for ident in identities:
    now_tick = tick(ident['pid'])
    item = {'original': ident, 'current_start_ticks': now_tick, 'closed': now_tick != ident['start_ticks']}
    closed.append(item)
    ck('original_PID_closed:' + str(ident['pid']), item['closed'])
ck('same_original_case_seed_prefix', c['case_sha256'] == old['case_sha256'] == sha(c['case_path']) and c['condition']['seed'] == old['condition']['seed'] and c['condition']['prefix'] == old['condition']['prefix'])
ck('same_fork_worker_and_base', all(c[k] == old[k] for k in ['fork_phase', 'fork_slot', 'worker', 'B', 'H150', 'continuation_policy']))
ck('exposed_scope_no_extra_independent_case', c['scientific_branch'] == 'EXPOSED_POSTVALIDATION_IMPLEMENTATION_CAPABILITY_DIAGNOSTIC_NOT_GENERALIZATION' and c['postvalidation_applicability_probe']['original_group'] == OLD)
spec = c['postvalidation_applicability_probe']
for ref in [spec['runtime_approval'], spec['recipe_catalog'], spec['original_B_result']]:
    pin(ref, job)
catalog = read(spec['recipe_catalog']['path'])
menu = read('freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json')
ck('unique_five_fixed_tags', [x['tag'] for x in c['actions']] == TAGS and [x['tag'] for x in catalog['rows']] == TAGS and catalog['model_labels_or_choices_transferred'] is False)
original_sources = ['source/v8_worker_v2.py', 'runtime/control/base_campaign.py', 'runtime/code/stream_runtime_evidence.py']
new_sources = ['source/v8_postapp_fixed_v2.py', 'families/critic_value/postvalidation_applicability_probe_v1/fixed_sequence_candidate_v2.py', 'families/critic_value/postvalidation_applicability_probe_v1/root_wrapper_candidate_v2.py']
for path in original_sources:
    ck('original_source_same_both_jobs:' + path, sha(path) == job['files'].get(path) == oldjob['files'].get(path))
for path in new_sources:
    ck('new_source_job_exact:' + path, sha(path) == job['files'].get(path))
before = read('analysis/' + GROUP + '_POSTAPP_FIXED_BEFORE_B.json')
ck('fixed_before_B_owner_source_and_no_model', before['owner_pid'] == sup['worker']['pid'] and before['catalog'] == catalog and before['source_job_sha256'] == refs['jobs/' + GROUP + '/SOURCE_MANIFEST.json'] and before['supervisor_sha256'] == refs['owned/' + GROUP + '_SUPERVISOR.json'] and before['counts']['physical_proposals_yielded'] == 0 and before['not_model_choices'] is True)
for record in before['mandatory_closed']:
    g = record['group']
    begin = read('owned/' + g + '_SUPERVISOR.json')
    closed_end = read('owned/' + g + '_SUPERVISOR_END.json')
    ck('original_mandatory_closed_before_new_job:' + g, record['begin_sha256'] == refs['owned/' + g + '_SUPERVISOR.json'] and record['end_sha256'] == refs['owned/' + g + '_SUPERVISOR_END.json'] and closed_end['state'] == 'STOP' and closed_end['worker_exit_code'] == 0 and closed_end['survivors'] == [] and closed_end['ended_unix'] < sup['started_unix'])

# Global event stream is filtered before JSON parsing; only this closed group's raw lines are retained.
events = {}
with (P / 'runtime/ATTEMPTS.jsonl').open('rb') as stream:
    for line in stream:
        if ('"' + GROUP + '_').encode() not in line:
            continue
        event = json.loads(line)
        if not event.get('id', '').startswith(GROUP + '_'):
            continue
        key = event['id'] + ':' + event['event']
        ck('scoped_event_unique:' + key, key not in events)
        events[key] = {'record': event, 'raw_line_sha256': hashlib.sha256(line).hexdigest()}
ck('six_START_END_pairs', len(events) == 12 and len([x for x in events if x.endswith(':START')]) == 6)
for tag in ['parent'] + TAGS:
    ident = GROUP + '_' + tag
    s, e = events[ident + ':START']['record'], events[ident + ':END']['record']
    ck('event_exact_config_job_and_join:' + tag, s['config_sha256'] == refs['experiments/' + GROUP + '.json'] and s['job_source_sha256'] == refs['jobs/' + GROUP + '/SOURCE_MANIFEST.json'] and e['joined'] is True and e['returncode'] == 0 and e['unix'] > s['unix'])
    if tag != 'parent':
        ck('original_parent_hash_equal:' + tag, e['parent_hash_equal'] is True)

bgate = read('analysis/' + GROUP + '_POSTAPP_B_RAW_GATE.json')
entered = read('analysis/' + GROUP + '_POSTAPP_B_RAW_COMPARE_ENTERED.json')
proof = bgate['actual_loaded_compare_proof']
ck('B_original_full_raw_gate_PASS', bgate['original_compare_result']['status'] == 'PASS' and bgate['original_compare_result']['errors'] == [] and all(x is True for x in bgate['original_compare_result']['trace_fields'].values()))
ck('B_gate_source_config_identities', bgate['old_config_sha256'] == refs['experiments/' + OLD + '.json'] and bgate['new_config_sha256'] == refs['experiments/' + GROUP + '.json'] and bgate['old_job_source_sha256'] == refs['jobs/' + OLD + '/SOURCE_MANIFEST.json'] and bgate['new_job_source_sha256'] == refs['jobs/' + GROUP + '/SOURCE_MANIFEST.json'] and bgate['case_sha256'] == c['case_sha256'] and bgate['seed'] == c['condition']['seed'] and bgate['prefix'] == c['condition']['prefix'])
ck('actual_loaded_original_compare_code_proof', proof['CodeType_value_equal'] is True and proof['all_noncallable_co_fields_and_nested_constant_values_equal'] is True and proof['actual_function_globals_is_original_module'] is True and proof['raw_marshal_equality_not_a_gate'] is True and proof['AST_full_module_compile_only_no_exec'] == 1 and proof['actual_canonical_code_value_sha256'] == proof['expected_full_module_code_value_sha256'] and proof['actual_loaded_module'] == proof['actual_co_filename'] == str(P / 'runtime/control/base_campaign.py') and proof['actual_module_source_sha256'] == refs['runtime/control/base_campaign.py'] and proof['helper_actual_code_file'] == str(P / 'runtime/code/stream_runtime_evidence.py') and proof['helper_source_sha256'] == refs['runtime/code/stream_runtime_evidence.py'])
ck('one_original_comparison_before_remaining_yields', bgate['counts']['physical_proposals_yielded'] == 1 and bgate['counts']['original_compare_raw_entered'] == 1 and bgate['counts']['original_compare_raw_returned'] == 1)
final = read('analysis/' + GROUP + '_POSTAPP_FINAL.json')
ck('fivecompleted_and_no_model_map_fit', set(final['completed']) == set(TAGS) and final['NOT_RUN'] == [] and final['stop'] is None and final['counts']['physical_proposals_yielded'] == 5 and final['counts']['original_compare_raw_entered'] == 1 and final['counts']['original_compare_raw_returned'] == 1 and final['counts']['model_initialize_restore_forward_score_fit_RNG_map'] == 0 and final['counts']['new_scorer_or_direct_physics_calls'] == 0)

rows, timing, replays = [], [], []
for tag in ['parent'] + TAGS:
    repath = 'audit/scorer_replay/' + GROUP + '_' + tag + '.json'
    replay = read(repath)
    ck('original_replay_exact_PASS:' + tag, replay['status'] == 'SCORER_REPLAY_PASS' and replay['errors'] == [] and replay['original_result_exact_reproduced'] is True)
    for path, digest in replay['unchanged_scorer_sources'].items():
        ck('unchanged_scorer_both_source_pins:' + tag + ':' + path, sha(path) == digest == job['files'].get(path) == oldjob['files'].get(path))
    replays.append({'tag': tag, 'ref': {'path': repath, 'sha256': refs[repath]}, 'qualified': replay['qualified_replay'], 'original_result_exact_reproduced': replay['original_result_exact_reproduced'], 'input_refs_record_only_no_raw_opened': replay['input_sha256']})
    if tag == 'parent':
        continue
    index = TAGS.index(tag)
    cat = catalog['rows'][index]
    original_tag = cat['original_tag']
    orig_recipe = menu['action_contracts'][index]
    expected = copy.deepcopy(orig_recipe)
    if tag != 'B':
        expected['action']['terminal_timing_applicability'] = True
    ck('exact_full_recipe_only_flag_clone:' + tag, cat['full_recipe'] == expected and cat['old_recipe_sha256'] == menu['full_recipe_sha256'][index] and cat['original_label_not_valid_for_new_recipe'] is (tag != 'B') and cat['recipe_sha256'] != cat['old_recipe_sha256'] if tag != 'B' else cat['full_recipe'] == expected and cat['recipe_sha256'] == cat['old_recipe_sha256'])
    rowpath = 'attempts/' + GROUP + '_' + tag + '_RESULT.json'
    oldpath = 'attempts/' + OLD + '_' + original_tag + '_RESULT.json'
    row, oldrow = read(rowpath), read(oldpath)
    ck('actual_result_recipe_id_and_action:' + tag, row['action'] == expected['action'] and row['prediction']['full_recipe_sha256'] == cat['recipe_sha256'] and row['prediction']['fixed_not_learned'] is True and row['prediction']['original_model_labels_not_transferred'] is True)
    branch = read('analysis/' + GROUP + '_POSTAPP_BRANCH_' + tag + '.json')
    metricpath = row['metrics_path']
    metric = read(metricpath)
    common = metric['native_physical_audit']['unchanged_evaluator']['physical_task_result']['scorer_v2_common_conditions']
    common = {x: common.get(x) for x in HARD}
    ck('original11hardTrue_and_hardFalse:' + tag, all(common[x] is True for x in HARD) and branch['hard_conditions'] == common and branch['true_hard_safety_violation'] is False)
    ck('original_branch_refs_exact:' + tag, branch['original_row'] == row and branch['original_result']['path'] == rowpath and branch['original_result']['sha256'] == refs[rowpath] and branch['safety_source']['path'] == metricpath and branch['safety_source']['sha256'] == refs[metricpath] and branch == final['completed'][tag])
    ck('original_catalog_label_ref_preserved:' + tag, cat['original_result_reference_only'] == {'path': oldpath, 'sha256': refs[oldpath]})
    ck('complete_qualified_and_cost_replay_exact:' + tag, row['complete'] is True and row['qualified'] is replay['qualified_replay'] and row['JF'] == replay['independent_JF'] and row['JM'] == replay['independent_JM'] and row['motion_vs_B']['failed_requirements'] == replay['motion_replay']['failed_requirements'])
    newbinding = read('attempts/' + GROUP + '_' + tag + '_EXECUTION_BINDING.json')
    oldbinding = read('attempts/' + OLD + '_' + original_tag + '_EXECUTION_BINDING.json')
    strip_id = lambda x: {k: v for k, v in x.items() if k != 'id'}
    ck('actual_binding_exactflag_and_same_candidate:' + tag, newbinding['action'] == expected['action'] == c['actions'][index]['action'] and oldbinding['action'] == orig_recipe['action'] and strip_id(newbinding['candidate']) == strip_id(oldbinding['candidate']) and newbinding['truth_used'] is False and oldbinding['truth_used'] is False)
    execution = lambda r: [{'decision_index': x['decision_index'], 'activated': x.get('activated'), 'modal_present': x.get('modal') is not None, 'legacy_status': (x.get('legacy') or {}).get('status'), 'reference_start_s': x.get('reference_start_s'), 'reference_end_s': x.get('reference_end_s')} for x in r.get('execution', [])]
    item = {'tag': tag, 'old_tag': original_tag, 'old_complete': oldrow['complete'], 'old_qualified': oldrow['qualified'], 'new_complete': row['complete'], 'new_qualified': row['qualified'], 'old_JF': oldrow['JF'], 'old_JM': oldrow['JM'], 'new_JF': row['JF'], 'new_JM': row['JM'], 'old_motion_failed_requirements': oldrow['motion_vs_B']['failed_requirements'], 'new_motion_failed_requirements': row['motion_vs_B']['failed_requirements'], 'hard11': common, 'true_hard_safety_violation': branch['true_hard_safety_violation'], 'actual_new_native_steps': row['actual_new_native_steps'], 'old_result': {'path': oldpath, 'sha256': refs[oldpath]}, 'new_result': {'path': rowpath, 'sha256': refs[rowpath]}, 'old_execution': execution(oldrow), 'new_execution': execution(row), 'old_timing_applicability': 'NOT_CAPTURED_FLAG_NOT_ENABLED', 'old_recipe_sha256': cat['old_recipe_sha256'], 'new_recipe_sha256': cat['recipe_sha256']}
    ck('old_timing_receipt_absent_no_predicate_inference:' + tag, not (P / ('history/' + OLD + '_' + original_tag + '_TIMING_APPLICABILITY.json')).exists())
    if tag == 'B':
        ck('own_B_qualified_and_original_label_exact', row['qualified'] is True and oldrow['qualified'] is True and row['JF'] == oldrow['JF'] and row['JM'] == oldrow['JM'])
        for key in ['original_B_result', 'new_B_result']:
            ck('B_gate_result_pin:' + key, sha(bgate[key]['path']) == bgate[key]['sha256'])
    else:
        tp = 'history/' + GROUP + '_' + tag + '_TIMING_APPLICABILITY.json'
        td = read(tp)
        ck('actual_RETURN5_single_causal_skip:' + tag, td['policy'] == 'CAUSAL_OPTIONAL_TIMING_APPLICABILITY_V1' and len(td['rows']) == 1 and all(r['phase'] == 'RETURN' and r['slot'] == 5 and r['knee_at_public_goal'] is False and r['knee_reference_stationary'] is True and r['optional_timing_requested'] is False and r['original_threshold'] == 1e-10 and r['truth_used'] is False and r['model_calls'] == 0 and r['original_terminal_assertions_unchanged'] is True for r in td['rows']))
        timing.append({'tag': tag, 'ref': {'path': tp, 'sha256': refs[tp]}, 'original_record': td})
    rows.append(item)

parentdata = read('runtime/output/' + GROUP + '_parent_DATA.json')
native = {'parent_actual_new_native_physics_steps': parentdata['metric']['actual_new_native_physics_steps'], 'children_actual_new_native_steps': {r['tag']: r['actual_new_native_steps'] for r in rows}, 'scope': '逐原字段抄录；父/子付费不含重复继承前缀，不把B raw identity 116320行和5817回执重复计物理。未重算raw。'}
original_resources = {}
for rp in ['audit/' + GROUP + '_EXTERNAL_RESOURCE_V1.txt', 'audit/' + GROUP + '_RAW_REPLAY_EXTERNAL_RESOURCE_V1.txt']:
    original_resources[rp] = {'text': raw(rp).decode(), 'sha256': refs[rp]}
read('audit/' + GROUP + '_MAIN_PHYSICS_APPROVAL_V1.json')
sha('families/critic_value/analysis/postapp01_closed_metadata_review_v1/RESULT.json')
result = {'schema': 'v8.POSTAPP02.closed_metadata_independent_review.v1', 'status': 'PASS_SCOPED_METADATA_NOT_NONB_MOTION_QUALIFICATION' if not [x for x in checks if not x['PASS']] else 'FAILED_METADATA_CHECKS', 'created_unix': time.time(), 'group': GROUP, 'checks': checks, 'failed_checks': [x for x in checks if not x['PASS']], 'original_replay_closure_gate': {'path': gate_path, 'sha256': refs[gate_path], 'original': end_replay}, 'owner_identity_closure': closed, 'original_supervisor_END': end, 'exact_config_source': {'config_sha256': refs['experiments/' + GROUP + '.json'], 'job_source_manifest_sha256': refs['jobs/' + GROUP + '/SOURCE_MANIFEST.json'], 'original_config_sha256': refs['experiments/' + OLD + '.json'], 'original_job_source_manifest_sha256': refs['jobs/' + OLD + '/SOURCE_MANIFEST.json'], 'case_sha256': c['case_sha256'], 'seed': c['condition']['seed'], 'prefix': c['condition']['prefix'], 'new_independent_case_count': 0}, 'old_new_five_results': rows, 'six_original_replay_labels': replays, 'original_B_cross_job_raw_gate': bgate, 'actual_applicability_receipts': timing, 'counts_scope': {'original_sequence': final['counts'], 'this_audit_model_scoring_rawcompare_physics_fit_RNG_calls': 0, 'actual_skipped_optional_timing_requests_from_four_boolean_receipts': 4}, 'original_native_increment_metadata': native, 'original_resources': original_resources, 'scoped_original_events': events, 'source_and_metadata_SHA256': refs, 'scientific_conclusions': ['仅B合格，四新nonB均完整但motion不合格；六份原回放PASS只表明原标签复现', '原VAL04 EARLY/LATE H150和LATE_PHASE合格，开关版本均变为motion失败；EARLY_PHASE原本加速度p95失败，现仍失败且失败项更多', '实际四份RETURN slot5回执为knee_at_public_goal=False、knee_reference_stationary=True、optional_timing_requested=False；只证明此保守启发式跳过请求，不证明旧路径违反原assert或全局predicate修复', 'B full raw-match证明同case/seed/prefix的B可复现；没有新增四nonB旧新rawcompare，不伪称逐native因果差分', '原VAL04资格和冻结模型选择保留；不得把旧学习标签转移给_APPLICABILITY新recipe，不构成额外独立验证，所有家族仍NOT_FULLY_EXPLORED'], 'limitations': ['只读闭合metadata及源字节SHA，不打开raw/trace，不导入或执行候选/模型/scorer，不重算motion/成本/函数code', '原timing receipt缺失标NOT_CAPTURED_FLAG_NOT_ENABLED；不能据新记录反推原predicate或旧terminal assert不合法', '原gate无独立created_unix，以原counts=1/1及已冻结sequence顺序界定先于后续yield，不伪造mtime时间证据', '前置schema探索两次打印异常（None legacy和输出截断）均在只读元数据内；0模型/scorer/raw/physics，未更改科学记录'], 'audit_resource': {'pid': os.getpid(), 'start_ticks': tick(os.getpid()), 'python_executable': sys.executable, 'python_version': sys.version, 'affinity': sorted(os.sched_getaffinity(0)), 'AS_limit': list(resource.getrlimit(resource.RLIMIT_AS)), 'wall_s': time.monotonic() - t0, 'CPU_s': time.process_time() - cpu0, 'maxRSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'metadata_and_source_bytes_read': read_bytes, 'raw_trace_bytes_read': 0}}
put('RESULT.json', result)
lines = ['# POSTAPP02 闭合元数据独立审查', '', '原回放 END 为 PASS、六份缓存齐全后审查。'+result['status']+'；'+str(len(checks))+' 项检查，'+str(len(result['failed_checks']))+' 项失败。', '', '同原 VAL04 case/seed/prefix，B 原跨 job full-raw 比对 PASS，实际 loaded compare 原源码/CodeType 值证明及两 job pin 一致。owner STOP/exit0、六对 START/END joined、五 child parent hash 不变、原 PID/starttick 均闭合。', '', '| 原配方 → 新配方 | 原资格 | 新资格 | 原 JF / JM（抄录） | 新 JF / JM（抄录） | 新 motion 失败 |', '|---|---|---|---|---|---|']
for r in rows:
    lines.append('| '+r['old_tag']+' → '+r['tag']+' | '+str(r['old_qualified'])+' | '+str(r['new_qualified'])+' | '+str(r['old_JF'])+' / '+str(r['old_JM'])+' | '+str(r['new_JF'])+' / '+str(r['new_JM'])+' | '+(', '.join(r['new_motion_failed_requirements']) or '无')+' |')
lines += ['', '原 EARLY_H150 合格 1323.2139574827079 / 101.44771132880281；新 EARLY_H150_APPLICABILITY 为 1323.2513097001054 / 101.50423541091276，完整但 excursion 失败。原 LATE_H150 与 LATE_PHASE 也从合格变为不合格。该开关改变了原本有效路径，不能称普遍修复。', '', '四个新 nonB 各有一条实际 RETURN slot 5 记录：knee_at_public_goal=False、knee_reference_stationary=True、optional_timing_requested=False、threshold=1e-10、truth_used=False、model_calls=0、原 terminal assertions 不变。原四配方没有对应 capture；不将缺失补成旧 predicate True/False。原执行 binding/candidate 除 action flag 和新身份外一致；RESULT.execution 的 decision_index/激活/参考时间字段保存在 JSON，不据其重算物理。', '', '全部五 child 原 11 hard 条件 True，joined true_hard_safety_violation=False；这不替代 motion 资格。六份 scorer replay 精确复现原标签与成本，不是四个新 nonB 合格。B 原 compare 116320 native rows/5817 receipts 为身份覆盖，不是额外推进。原 parent 实际新步 '+str(native['parent_actual_new_native_physics_steps'])+'；五 child 各 '+str(rows[0]['actual_new_native_steps'])+'，仅按原增量字段抄录。', '', '该分支是已暴露相同条件的固定实现能力诊断，独立新条件数 0，模型/拟合/映射/RNG 调用 0；未将旧冻结选择套到新 recipe。成本仅描述完整未合格执行，不计合格增量或胜出。全部家族仍 NOT_FULLY_EXPLORED。', '', '本次独立审查 0 raw/trace、0 新 compare/scorer/model/physics；资源和全部原路径 SHA 见 RESULT.json。source 值证明引用原执行回执，未新编译或调用函数。']
with (OUT / 'REPORT.md').open('x') as f:
    f.write('\n'.join(lines) + '\n')
manifest = {'schema': 'v8.POSTAPP02.review.actual_manifest.v1', 'result_sha256': hashlib.sha256((OUT / 'RESULT.json').read_bytes()).hexdigest(), 'report_sha256': hashlib.sha256((OUT / 'REPORT.md').read_bytes()).hexdigest(), 'audit_source_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), 'status': result['status'], 'checks': len(checks), 'failed': len(result['failed_checks']), 'scientific_execution_calls': 0}
put('ACTUAL_MANIFEST.json', manifest)
print(json.dumps(manifest, ensure_ascii=False))
raise SystemExit(0 if not result['failed_checks'] else 1)
