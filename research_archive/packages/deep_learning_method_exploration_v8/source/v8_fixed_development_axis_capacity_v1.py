"""SOURCE_ONLY future exact-byte thin root wrapper; no import-time work."""
from pathlib import Path
import hashlib
import importlib.util
import os

DEST="source/v8_fixed_development_axis_capacity_v1.py"
SOURCE="families/ppo_reward/continuous_scale_v1/development_axis_capacity_v1/fixed_axis_sequence_candidate_v1.py"
SOURCE_SHA="7eb4d9b0d497854f4dd4ca9292f0982d10fbcee536f478fa41ec604ba963faf2"

def sequence(study,config):
    owner_pid=os.getpid();inner=None
    try:
        package=Path(os.environ["ACL2_PACKAGE"]).resolve()
        def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if (Path(__file__).resolve()!=package/DEST or config.get("algorithm")!="v8_fixed_development_axis_capacity_v1" or
            config["frozen_artifacts"].get(DEST)!=sha(__file__) or config["frozen_artifacts"].get(SOURCE)!=SOURCE_SHA or sha(package/SOURCE)!=SOURCE_SHA):raise ValueError("EXACT_MAIN_REVIEWED_DEV_CAPACITY_ROOT_WRAPPER_SEQUENCE")
        spec=importlib.util.spec_from_file_location("_fixed_dev_capacity_"+config["group"],package/SOURCE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        inner=module.sequence(study,config);yield from inner
    except GeneratorExit:
        if os.getpid()!=owner_pid:return
        raise
    finally:
        if os.getpid()==owner_pid and inner is not None:inner.close()
