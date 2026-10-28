"""V2 source candidate: freeze matched selectors and reviewed extensions before B.

No environment or learner is created by this module. Actual use requires a
separately frozen config/model inventory and root physical dispatch approval.
"""
from pathlib import Path
import copy
import importlib.util
import json
import os
import sys
import time

P = Path(os.environ['ACL2_PACKAGE'])
from acl2_shared import append, put, sha


def load(relative):
    return json.loads((P / relative).read_text())


def module_at(name, relative):
    path = (P / relative).resolve()
    assert path.is_relative_to(P.resolve())
    assert name not in sys.modules, 'FRESH_VALIDATION_MODULE_NAMESPACE_REQUIRED'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sequence(study, config):
    owner_pid = os.getpid()

    def owner():
        assert os.getpid() == owner_pid, 'FORK_CHILD_HAS_NO_SELECTOR_WRITE_AUTHORITY'

    def save(relative, value):
        owner()
        put(relative, value)

    owner()
    assert not study.metrics and study.child is None and study.fork_done is True
    assert config['fork_phase'] == 'OUTBOUND' and config['fork_slot'] == 0
    spec = config['comparative_validation']
    assert spec['status'] == 'APPROVED_BY_MAIN_AGENT'
    assert spec['no_training'] is True and spec['no_outcome_reselection'] is True
    for relative, expected in config['frozen_artifacts'].items():
        assert sha(P / relative) == expected, 'VALIDATION_DEPENDENCY_CHANGED:' + relative
    group = config['group']
    decisions = {}
    counts = {'API_started': 0, 'API_returned': 0, 'new_fit': 0}

    def call(label, function, *args, **kwargs):
        owner()
        counts['API_started'] += 1
        append('analysis/' + group + '_INFERENCE_EVENTS.jsonl',
               {'event': 'START', 'label': label, 'unix': time.time(), 'owner_pid': owner_pid})
        result = function(*args, **kwargs)
        counts['API_returned'] += 1
        receipt_path = 'analysis/' + group + '_API_RETURN_' + str(counts['API_started']).zfill(3) + '.json'
        save(receipt_path, {'schema': 'v8.completed_inference_return_receipt.v1',
             'label': label, 'owner_pid': owner_pid, 'returned_unix': time.time(),
             'macro_counts_at_return': copy.deepcopy(counts), 'original_return_value': result})
        append('analysis/' + group + '_INFERENCE_EVENTS.jsonl',
               {'event': 'RETURN', 'label': label, 'unix': time.time(), 'owner_pid': owner_pid,
                'receipt': {'path': receipt_path, 'sha256': sha(P / receipt_path)}})
        return result

    try:
        adapter = module_at('_v8_validation_a3_adapter', spec['A_parallel_adapter'])
        parallel = call('A_PARALLEL_WRAPPER', adapter.predict_before_B, P, config, study)
        decisions.update(parallel['decisions'])
        sys.path.insert(0, str(P / 'families/critic_value/source'))
        from value_api import to_context25
        from controls_api import predict_control
        context = to_context25(study.prefork_causal_context)
        menu = load(spec['menu_path'])['action_contracts']
        tags = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
        sys.path.insert(0, str(P / 'families/ppo_reward'))
        from categorical_policy import digest, select_out0
        hashes = [digest(recipe) for recipe in menu]
        by_hash = dict(zip(hashes, tags))

        def keep(label, recipe_hash, prediction):
            assert label not in decisions and recipe_hash in by_hash
            index = hashes.index(recipe_hash)
            decisions[label] = {'choice_tag': tags[index], 'choice_recipe_sha256': recipe_hash,
                                'choice_action': copy.deepcopy(menu[index]['action']),
                                'prediction': prediction, 'original_qualification_granted': False}

        controls = load(spec['A1_controls'])
        for label in ['BEST_FIXED_TRAIN', 'IF_STUMP_TRAIN', 'NEAREST_CONTEXT']:
            prediction = call('A1_' + label, predict_control, controls, context, control=label)
            choice = prediction.get('choice_recipe_sha256') or hashes[0]
            keep('A1_' + label, choice, prediction)
        for item in spec['categorical_checkpoints']:
            document = load(item['path'])
            policy = document['policy']
            assert policy['action_contracts'] == menu
            prediction = call(item['label'], select_out0, policy, context['feature_names'],
                              context['features'], qa_validated=True)
            keep(item['label'], prediction['full_recipe_sha256'], prediction)
        aggregation = module_at('_v8_validation_bc_aggregation', spec['BC_aggregation_API'])
        for item in spec['BC_aggregation_bundles']:
            document = load(item['path'])
            prediction = call(item['label'], aggregation.select_out0, document['bundle'],
                              context['feature_names'], context['features'], qa_validated=True,
                              expected_bundle_sha256=document['bundle_object_sha256'],
                              frozen_recipe_sha256=hashes)
            keep(item['label'], prediction['full_recipe_sha256'], prediction)
        extension_records = {}
        for extension in spec.get('parallel_selector_adapters', []):
            label = extension['label']
            assert label not in extension_records
            extension_module = module_at('_v8_validation_extension_' + label, extension['path'])
            result = call(label, extension_module.predict_before_B, P, config, study)
            assert result['decisions'] and not study.metrics
            for selector, decision in result['decisions'].items():
                assert selector not in decisions
                index = hashes.index(decision['choice_recipe_sha256'])
                assert decision['choice_tag'] == tags[index]
                assert decision['choice_action'] == menu[index]['action']
                decisions[selector] = decision
            extension_records[label] = result
        save('predictions/' + group + '_FROZEN_CONTEXT_DECISIONS.json',
             {'created_unix': time.time(), 'owner_pid': owner_pid, 'context25': context,
              'A_source_proof_audit': parallel, 'extension_records': extension_records, 'decisions': decisions, 'counts': counts,
              'nested_A_inference_API_calls': parallel['inference_API_calls'],
              'before_any_candidate_outcome': True, 'new_training': False,
              'checkpoint_and_model_inventory_frozen_in_config': True})
        actions = config['actions']
        assert [a['tag'] for a in actions] == tags
        assert [a['action'] for a in actions] == [r['action'] for r in menu]
        selected = {tag: [label for label, d in decisions.items() if d['choice_tag'] == tag]
                    for tag in tags}
        history_decisions = {}
        for action in actions:
            owner()
            tag = action['tag']
            proposal = copy.deepcopy(action)
            proposal['prediction'] = {'selected_by': selected[tag],
                                      'recipe_sha256': hashes[tags.index(tag)],
                                      'all_A_B_D_decisions_frozen_before_B': True}
            yield proposal
            owner()
            assert study.last_row['id'] == group + '_' + tag
            if tag == 'B':
                assert study.last_row['complete'] and study.last_row['qualified']
                if spec.get('history_snapshot'):
                    sys.path.insert(0, str(P / 'families/history_conditioned'))
                    from completed_history_reader import load_completed_b_history
                    from c3b_inference import select
                    import completed_history_reader as history_reader_module
                    import c3b_inference as history_inference_module
                    import trial_interface as history_interface_module
                    loaded_history_sources = {}
                    for loaded, relative in [
                        (history_reader_module, 'families/history_conditioned/completed_history_reader.py'),
                        (history_inference_module, 'families/history_conditioned/c3b_inference.py'),
                        (history_interface_module, 'families/history_conditioned/trial_interface.py'),
                    ]:
                        actual_path = Path(loaded.__file__).resolve()
                        assert actual_path == (P / relative).resolve(), 'WRONG_LOADED_HISTORY_MODULE:' + relative
                        assert sha(actual_path) == config['frozen_artifacts'][relative]
                        loaded_history_sources[relative] = {'actual_loaded_path': str(actual_path), 'sha256': sha(actual_path)}
                    save('predictions/' + group + '_HISTORY_MODULE_SOURCE_BINDING.json',
                         {'owner_pid': owner_pid, 'actual_modules': loaded_history_sources, 'new_model_calls': 0})
                    completed = load_completed_b_history(P, group, config=config,
                                                         expected_case_sha256=config['case_sha256'])
                    snapshot = load(spec['history_snapshot'])
                    assert snapshot['recipe_hashes'] == hashes[:3], 'C3B_ORIGINAL_THREE_RECIPE_PERMISSION'
                    for method in ['ACTION_ONLY', 'HISTORY_ADDITIVE', 'HISTORY_INTERACTION',
                                   'HISTORY_DISABLED', 'COMMISSIONED25_INTERACTION']:
                        kwargs = {'model_id': method, 'expected_recipe_hashes': snapshot['recipe_hashes']}
                        if method == 'HISTORY_DISABLED':
                            kwargs['history'] = None
                        elif method == 'COMMISSIONED25_INTERACTION':
                            kwargs['commissioned25'] = context['features']
                        else:
                            kwargs['history'] = completed['history']
                        prediction = call('C_' + method, select, snapshot, **kwargs)
                        assert prediction['selected_recipe_sha256'] in by_hash
                        history_decisions[method] = prediction
                    save('predictions/' + group + '_FROZEN_HISTORY_DECISIONS.json',
                         {'history': completed, 'decisions': history_decisions,
                          'B_complete_before_selection': True, 'scope': 'COLD_REPLAY_NOT_CONTINUOUS_TRIAL'})
                    if any(d['selected_tag'] == 'B' for d in history_decisions.values()):
                        yield {'tag': 'HISTORY_B', 'action': {'family': 'B'},
                               'category': 'COLD_REPLAY_POST_HISTORY_CONTROL', 'repeat_of': 'B',
                               'prediction': {'recipe_sha256': hashes[0], 'decision_after_B': True,
                                              'selected_by_C_models': [name for name, d in history_decisions.items() if d['selected_tag'] == 'B']}}
                        owner()
                        assert study.last_row['id'] == group + '_HISTORY_B'
                        assert study.last_row['complete'] and study.last_row['qualified']
        save('analysis/' + group + '_SELECTOR_EXECUTION_LINK.json',
             {'decisions': decisions, 'history_decisions': history_decisions, 'counts': counts,
              'rows_by_tag': {r['id'].removeprefix(group + '_'): r['id'] for r in study.metrics},
              'all_context_decisions_before_B': True, 'no_outcome_based_reselection': True,
              'same_recipe_not_independent_replication': True, 'real_physical_attempts_saved': 0,
              'root_parent_closure_and_raw_replay_still_required': True})
    except GeneratorExit:
        if os.getpid() == owner_pid:
            save('analysis/' + group + '_SELECTOR_OWNER_CLOSE.json',
                 {'status': 'OWNER_CLOSED_PRESERVE_EVIDENCE', 'counts': counts})
        return
    except BaseException as error:
        if os.getpid() != owner_pid:
            return
        save('analysis/' + group + '_SELECTOR_ERROR.json',
             {'error_type': type(error).__name__, 'error': str(error), 'counts': counts,
              'failed_nested_API_work_must_not_be_reported_as_zero': True})
        raise
