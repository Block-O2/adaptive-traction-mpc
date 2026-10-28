"""A3准入：实际原payload+外层owner测得source proof；无模型/I/O。"""
from scoped_subset_api import SUBSETS, to_subset

FEATURE_NAMES=SUBSETS['WRENCH39']


def to_context_full(payload, source_profiles, source_proof=None):
    assert isinstance(payload,dict) and 'labels_evaluation_only' not in payload
    if set(payload)=={'raw_payload','source_proof'}:
        assert source_proof is None
        source_proof=payload['source_proof'];payload=payload['raw_payload']
    assert isinstance(source_proof,dict) and source_profiles
    assert any(source_proof==profile for profile in source_profiles),'A3_CAPTURE_CALLBACK_OBSERVER_RUNTIME_SOURCE_IDENTITY'
    assert set(source_proof)=={'capture','runtime','observer','observation_contract','history_guard','runtime_loader','callback'}
    scoped=to_subset(payload,'WRENCH39')
    assert scoped['feature_names']==FEATURE_NAMES
    return scoped
