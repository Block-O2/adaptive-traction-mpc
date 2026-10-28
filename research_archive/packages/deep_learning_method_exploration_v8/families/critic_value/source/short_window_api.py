"""需要付费真实候选rollout的短窗对照；不接收完整未来资格/成本。"""


def select_short(records, horizon_s):
    """records须为同真实父状态、同H、已完成H窗口的measured成本回执。"""
    assert records
    assert len({r['parent_hash'] for r in records}) == 1
    assert all(abs(r['horizon_s'] - horizon_s) < 1e-9 for r in records)
    assert all(r['actual_window_complete'] and not r.get('future_outcome_used', False) for r in records)
    assert all('qualified' not in r and 'full_JF' not in r and 'full_JM' not in r for r in records)
    chosen = min(records, key=lambda r: (r['short_JF_N_s'], r['recipe_sha256']))
    return {'choice_recipe_sha256': chosen['recipe_sha256'], 'horizon_s': horizon_s,
            'requires_real_candidate_physics': True, 'cheap_prediction': False,
            'future_qualification_mask_used': False,
            'actual_candidate_window_count': len(records),
            'efficiency_scope': '所有候选H窗口都须实际采集；完整菜单已经执行后的选择仅为回顾对照，不构成物理省试'}
