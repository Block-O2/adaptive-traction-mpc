import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'stages/stage5_personalized_motion_learning'

def load(path):
    spec=importlib.util.spec_from_file_location(path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_runners_resolve_this_checkout_and_frozen_source():
    historic=load(STAGE/'docs/safe_fallback_verification_v1/verification_runner.py')
    bench=load(STAGE/'docs/wsl_migration_v1/cross_host_benchmark_runner.py')
    assert historic.ROOT==ROOT
    assert bench.ROOT==ROOT
    freeze=json.loads((STAGE/'docs/safe_fallback_execution_v1/FREEZE_v1.json').read_text())
    assert historic.source()==freeze['source_fingerprint']
    assert bench.source_fingerprint()==freeze['source_fingerprint']

def test_benchmark_registry_has_exact_frozen_24_runs():
    bench=load(STAGE/'docs/wsl_migration_v1/cross_host_benchmark_runner.py')
    spec=json.loads((bench.DOC/'CROSS_HOST_BENCHMARK_V1.json').read_text())
    assert len(spec['run_order'])==24
    assert [r['case_id'] for r in spec['run_order'][::6]]==['low_ordinary','high_100_sync','high_120_sync','high_120_start_8_13']
    for row in spec['run_order']:
        assert bench.sha(ROOT/row['case'])==row['case_sha256']
