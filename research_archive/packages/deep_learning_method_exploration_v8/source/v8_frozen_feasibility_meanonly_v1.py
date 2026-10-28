"""SOURCE_ONLY future root thin wrapper; copy exact bytes only after main review.

Future destination: source/v8_frozen_feasibility_meanonly_v1.py.
No import-time model work, no direct environment/physics or result writes.
"""
from pathlib import Path
import hashlib
import importlib.util
import os

ROOT_DESTINATION = "source/v8_frozen_feasibility_meanonly_v1.py"
CANDIDATE = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_mean_deployment_v1/mean_sequence_candidate_v1.py"
CANDIDATE_SHA = "5ffc0f2f40d3db2120258c25421b822932be9e0a2e0b418124b8c853e36e2be9"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sequence(study, config):
    owner_pid = os.getpid(); inner = None
    try:
        package = Path(os.environ["ACL2_PACKAGE"]).resolve()
        if (Path(__file__).resolve() != package/ROOT_DESTINATION or
                config.get("algorithm") != "v8_frozen_feasibility_meanonly_v1" or
                config["frozen_artifacts"].get(ROOT_DESTINATION) != sha(__file__) or
                config["frozen_artifacts"].get(CANDIDATE) != CANDIDATE_SHA or sha(package/CANDIDATE) != CANDIDATE_SHA):
            raise ValueError("EXACT_MAIN_REVIEWED_NEW_ROOT_WRAPPER_AND_PRIVATE_SEQUENCE_REQUIRED")
        spec = importlib.util.spec_from_file_location("_root_frozen_feasibility_sequence_"+config["group"], package/CANDIDATE)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        inner = module.sequence(study, config)
        yield from inner
    except GeneratorExit:
        if os.getpid() != owner_pid:
            return
        raise
    finally:
        # yield-from forwards child GeneratorExit to the inner generator,
        # whose own owner guard is silent there. Only the real parent may
        # explicitly close it; this wrapper never writes shared artifacts.
        if os.getpid() == owner_pid and inner is not None:
            inner.close()
