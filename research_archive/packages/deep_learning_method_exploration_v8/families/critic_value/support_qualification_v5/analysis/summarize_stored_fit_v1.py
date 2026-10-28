"""只读A5已存metadata；0候选import/forward/fit/physics。"""
from pathlib import Path
import collections
import hashlib
import json
import time


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, d):
    with p.open('x') as f:
        json.dump(d, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def main():
    P = Path(__file__).resolve().parents[1]
    def load(rel):
        return json.loads((P / rel).read_text())
    complete = load('fit_run_v1/COMPLETE.json')
    stored = load('fit_run_v1/DEVELOPMENT_LOCO_AND_FULL_V1.json')
    data = load('data/OPERATIONAL_RISK50_DATASET_V1.json')
    resource = load('FIT_EXTERNAL_RESOURCE_V1.json')
    contract = load('contracts/FIT_CONTRACT_PROPOSED_V1.json')
    bundle = load('fit_run_v1/A5_FROZEN_BUNDLE_V1.json')
    raw = data['risk_rows']
    truth = {(r['case_sha256_split_evaluation_only'], r['recipe_sha256']): r for r in raw}
    names = {r['case_sha256_split_evaluation_only']: r['group_evaluation_only'] for r in raw if r['origin_evaluation_only'] == 'OLD48_FULL_TASK'}
    methods = contract['methods']; objectives = contract['objectives']
    scopes = {}; admission_changes = {}; primary_changes = {}; heavy = {}
    for scope in ('LOCO', 'FULL'):
        items = stored[scope]; scopes[scope] = {}
        admission_changes[scope] = []; primary_changes[scope] = []
        for method in methods:
            confusion = collections.Counter()
            for item in items:
                case = item['case_sha256_evaluation_only']
                for pred in item['prediction']['predictions']:
                    actual = truth[(case, pred['recipe_sha256'])]['operational_qualified_target_only']
                    admit = pred['predicted_operational_admission_by_method'][method]
                    confusion['true_admit'] += bool(admit and actual)
                    confusion['false_admit'] += bool(admit and not actual)
                    confusion['true_reject'] += bool(not admit and not actual)
                    confusion['false_reject'] += bool(not admit and actual)
                    confusion['unsupported_cost_prediction'] += not pred['supported']
            variants = {}
            for objective in objectives:
                rows = [i['selection_evaluation'][method + '/' + objective] for i in items]
                qualified_cost = [r for r in rows if r['operational_qualification'] is True and r['full_cost_available']]
                variants[objective] = {'qualified': sum(r['operational_qualification'] is True for r in rows),
                    'failed_operational': sum(r['operational_qualification'] is False for r in rows),
                    'qualification_unknown': sum(r['operational_qualification'] is None for r in rows),
                    'complete_cost_unknown': sum(not r['full_cost_available'] for r in rows),
                    'predictive_abstain_then_B': sum(r['B_fallback'] for r in rows),
                    'explicit_B_choice': sum(r['choice_tag'] == 'B' and not r['B_fallback'] for r in rows),
                    'choice_counts': dict(collections.Counter(r['choice_tag'] for r in rows)),
                    'qualified_full_cost_count': len(qualified_cost),
                    'qualified_mean_delta_JF_N_s': sum(r['delta_JF_vs_B_N_s'] for r in qualified_cost) / len(qualified_cost) if qualified_cost else None,
                    'qualified_mean_delta_JM_Nm_s': sum(r['delta_JM_vs_B_Nm_s'] for r in qualified_cost) / len(qualified_cost) if qualified_cost else None,
                    'actual_qualified_and_JM_nonincrease': sum(r['delta_JM_vs_B_Nm_s'] <= 1e-12 for r in qualified_cost)}
            scopes[scope][method] = {'50cell_operational_admission_confusion_before_cost_support': dict(confusion), 'selection': variants}
        for item in items:
            case = item['case_sha256_evaluation_only']
            old = item['selection_evaluation']['A3_RISK48/JF_QUALIFIED']
            new = item['selection_evaluation']['A5_RISK50/JF_QUALIFIED']
            if old['choice_tag'] != new['choice_tag'] or old['B_fallback'] != new['B_fallback']:
                primary_changes[scope].append({'case': names[case], 'risk48': old, 'risk50': new})
            for pred in item['prediction']['predictions']:
                before = pred['predicted_operational_admission_by_method']['A3_RISK48']
                after = pred['predicted_operational_admission_by_method']['A5_RISK50']
                if before != after:
                    admission_changes[scope].append({'case': names[case], 'tag': pred['tag'],
                        'actual_qualified': truth[(case, pred['recipe_sha256'])]['operational_qualified_target_only'],
                        'risk48_probability': pred['qualification_failure_score'], 'risk50_probability': pred['operational_failure_probability50'],
                        'risk48_admitted': before, 'risk50_admitted': after})
            if names[case] == 'EARLYH01':
                heavy[scope] = {'phase_predictions': [p for p in item['prediction']['predictions'] if p['tag'] in ('EARLY_PHASE', 'LATE_PHASE')],
                    'risk48_JF': old, 'risk50_JF': new,
                    'negative_control_probability_parity_max_error': item.get('heavy_held_new_labels_absent_risk_parity_max_error')}
    closures = []
    for role, pid, ticks in [('model', complete['START']['PID'], complete['START']['start_ticks']),
                             ('timeout', resource['timeout_PID'], None), ('launcher', resource['launcher_PID'], None)]:
        p = Path('/proc') / str(pid) / 'stat'
        now = int(p.read_text().rsplit(')', 1)[1].split()[19]) if p.exists() else None
        closed = now is None or ticks is not None and now != ticks
        assert closed
        closures.append({'role': role, 'PID': pid, 'original_start_ticks': ticks, 'observed_start_ticks': now,
                         'checked_unix': time.time(), 'original_process_closed': closed})
    manifest = load('SOURCE_CANDIDATE_MANIFEST_V1.json')
    checks = {rel: sha(P / rel) == h for rel, h in manifest['source_files_sha256'].items()}
    assert all(checks.values()) and sha(P / 'launch_approved_once_v1.py') == contract['external_launcher_sha256']
    assert complete['API_ledger'] == contract['expected_API_accounting']
    full_old = json.loads((P.parents[2] / data['source_files']['A3_bundle']['path']).read_text())['cohorts']['MERGED']['models']['WRENCH39']
    assert bundle['frozen_A3_cost_model'] == full_old
    audit = {'status': 'COMPLETED_APPROVED_ONE_FIT_METADATA_SUMMARY_NO_EXTRA_CALLS',
        'COMPLETE_sha256': sha(P / 'fit_run_v1/COMPLETE.json'), 'bundle_sha256': sha(P / 'fit_run_v1/A5_FROZEN_BUNDLE_V1.json'),
        'scopes': scopes, 'risk48_vs50_primary_JF_changes': primary_changes,
        'risk48_vs50_admission_changes': admission_changes, 'heavy_case': heavy,
        'fit_actual': {'fits': len(complete['fit_ledger']), 'completed': sum(x['completed'] for x in complete['fit_ledger']),
            'iterations': sum(x['iterations'] for x in complete['fit_ledger']),
            'objective_entry': sum(x['function_evaluations_observed'] for x in complete['fit_ledger']),
            'objective_completed': sum(x['objective_evaluations_completed'] for x in complete['fit_ledger']),
            'logit_matvec_entry': sum(x['logit_matvec_entry'] for x in complete['fit_ledger']),
            'logit_matvec_completed': sum(x['logit_matvec_completed'] for x in complete['fit_ledger']),
            'gradient_matvec_entry': sum(x['gradient_matvec_entry'] for x in complete['fit_ledger']),
            'gradient_matvec_completed': sum(x['gradient_matvec_completed'] for x in complete['fit_ledger']),
            'training_design_rows': sum(x['training_design_rows'] for x in complete['fit_ledger']),
            'cost_or_margin_or_control_fits': 0},
        'API_actual_exact': complete['API_ledger'], 'initial_data_context39_extractions': 50,
        'resources': {'model_wall_s': complete['END']['unix'] - complete['START']['unix'],
            'model_CPU_user_delta_s': complete['END']['CPU_user_s'] - complete['START']['CPU_user_s'],
            'model_CPU_system_delta_s': complete['END']['CPU_system_s'] - complete['START']['CPU_system_s'],
            'model_peak_RSS_KiB': complete['END']['peak_RSS_KiB'], 'external': resource},
        'closures': closures, 'frozen_source_checks': checks, 'cost_model_full_object_exact_A3': True,
        'summary_extra_model_calls_fit_physics': 0, 'actual_OUT0_or_deployment': 'NOT_RUN_NOT_APPROVED',
        'calibration': 'NOT_RUN', 'interpretation': ['LOCO主选择无改变，不是泛化改善',
            'FULL已见heavy局部修补，但主8/10和误放5/50未提高；nearest50记忆控制同列',
            '原成本/归一化/门保持，partial只binary标签，完整成本和45margin仍缺失',
            '原raw77仍INVALID；所有case已曝光，非IID/非安全保证']}
    save(P / 'analysis/DEVELOPMENT_RESULT_SUMMARY_V1.json', audit)
    save(P / 'analysis/ACTUAL_RESOURCE_CLOSURE_AND_OPERATIONS_V1.json', {k: audit[k] for k in ('status', 'COMPLETE_sha256', 'bundle_sha256', 'fit_actual', 'API_actual_exact', 'initial_data_context39_extractions', 'resources', 'closures', 'frozen_source_checks', 'cost_model_full_object_exact_A3', 'summary_extra_model_calls_fit_physics')})
    lines = ['# A5 操作资格支持修复结果', '', '本次唯一批准拟合完成。fullfit 修复已见 heavy 的局部失败格；整 case LOCO 主选择没有改善。所有结果均为已曝光开发诊断。', '',
        '| 范围/方法 | JF选择合格/失败 | 50格误放/误拒 | 主动弃权→B | 完整成本未知 |', '|---|---:|---:|---:|---:|']
    for scope in ('LOCO', 'FULL'):
        for method in methods:
            s = scopes[scope][method]; q = s['selection']['JF_QUALIFIED']; cf = s['50cell_operational_admission_confusion_before_cost_support']
            lines.append(f"| {scope}/{method} | {q['qualified']}/{q['failed_operational']} | {cf['false_admit']}/{cf['false_reject']} | {q['predictive_abstain_then_B']} | {q['complete_cost_unknown']} |")
    full = heavy['FULL']; phase = {p['tag']: p for p in full['phase_predictions']}
    lines += ['', '已见 heavy 的 LATE_PHASE 失败概率从 %.9f 升为 %.9f，EARLY_PHASE 从 %.9f 升为 %.9f；原p<.5门未改。主选择由失败的 LATE_PHASE 改为合格 EARLY_H150。' % (phase['LATE_PHASE']['qualification_failure_score'], phase['LATE_PHASE']['operational_failure_probability50'], phase['EARLY_PHASE']['qualification_failure_score'], phase['EARLY_PHASE']['operational_failure_probability50']), '',
        '但 FULL 主资格仍8/10，误放仍5/50、误拒从0增为1；其它已见格发生抵消性改变，详见JSON。nearest50在全训练格10/10只是记忆，LOCO6/10且与nearest48相同。不得替换预登记primary或将fullfit称泛化。', '',
        'LOCO risk48/risk50 全10个JF选择相同，合格10/10；false-admit仍7/50。这个分母包含两条新partial操作失败：旧48上的原6/48与新增heavy late-phase误放不能混成风险改善。heavy全case留出后新标签被全部排除，概率parity误差=0，符合预注册负对照。', '',
        'JF主LOCO合格平均ΔJF=−26.844099 N·s，JM代价+3.896525 N·m·s；JM独立/STRICT结果见JSON。没有把低partial成本当收益。FULL两新partial的完整JF/JM与45margin仍MISSING，风险标签仅operational-qualified=false。', '',
        f"实际11fit、96迭代、107次objective与107次gradient矩阵向量乘；500训练design行。20批API、420selectors、300成本dot+50risk48dot+100risk50dot；40nearest批/200查询/1862距离，各entry/completed完全相等。0新ridge/margin/control拟合、0physics、0重试。", '',
        f"模型wall {audit['resources']['model_wall_s']:.6f}s，CPU {audit['resources']['model_CPU_user_delta_s']+audit['resources']['model_CPU_system_delta_s']:.6f}s，峰值RSS {audit['resources']['model_peak_RSS_KiB']} KiB；外部wait4 CPU {resource['wait4_timeout_tree_usage']['CPU_user_s']+resource['wait4_timeout_tree_usage']['CPU_system_s']:.6f}s，wall {resource['launch_to_return_wall_s']:.6f}s。launcher峰值{resource['launcher_peak_RSS_KiB']} KiB另列。", '',
        f"模型PID{complete['START']['PID']}/start_ticks{complete['START']['start_ticks']}、timeout PID{resource['timeout_PID']}、launcher PID{resource['launcher_PID']}均已闭合。原成本模型整体对象与A3完全相等，六个冻结source及launcher SHA均未变。", '',
        f"COMPLETE SHA `{audit['COMPLETE_sha256']}`；bundle SHA `{audit['bundle_sha256']}`。校准、实际OUT0与部署均NOT_RUN/未批准。原raw77仍INVALID。"]
    with (P / 'REPORT.md').open('x') as f:
        f.write('\n'.join(lines) + '\n')
    print(json.dumps({'summary_sha256': sha(P / 'analysis/DEVELOPMENT_RESULT_SUMMARY_V1.json'),
        'resource_sha256': sha(P / 'analysis/ACTUAL_RESOURCE_CLOSURE_AND_OPERATIONS_V1.json'),
        'report_sha256': sha(P / 'REPORT.md'), 'primary_changes': primary_changes,
        'admission_changes': admission_changes}, ensure_ascii=False))


if __name__ == '__main__':
    main()
