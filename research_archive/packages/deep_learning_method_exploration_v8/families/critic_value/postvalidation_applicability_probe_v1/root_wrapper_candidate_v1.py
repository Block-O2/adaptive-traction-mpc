"""SOURCE_ONLY root-copy candidate. No job preparation or direct physics dispatch."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

SEQUENCE = "families/critic_value/postvalidation_applicability_probe_v1/fixed_sequence_candidate_v1.py"
SEQUENCE_SHA = "43bb712b43aba24efbdca7671750364518153644d4366016cf15c752585ebe6b"

def sequence(study, config):
    package = Path(os.environ["ACL2_PACKAGE"]).resolve()
    actual = Path(__file__).resolve()
    if actual != package / "source/v8_postapp_fixed_v1.py":
        raise ValueError("ROOT_MUST_COPY_EXACT_REVIEWED_WRAPPER_BYTES_FIRST")
    job = json.loads((package / "jobs" / config["group"] / "SOURCE_MANIFEST.json").read_text())
    own = hashlib.sha256(actual.read_bytes()).hexdigest()
    if config["frozen_artifacts"].get("source/v8_postapp_fixed_v1.py") != job["files"].get("source/v8_postapp_fixed_v1.py") or job["files"].get("source/v8_postapp_fixed_v1.py") != own:
        raise ValueError("ACTUAL_ROOT_WRAPPER_NOT_JOB_FROZEN")
    target = package / SEQUENCE
    if hashlib.sha256(target.read_bytes()).hexdigest() != SEQUENCE_SHA or config["frozen_artifacts"].get(SEQUENCE) != SEQUENCE_SHA or job["files"].get(SEQUENCE) != SEQUENCE_SHA:
        raise ValueError("EXACT_NEW_FIXED_ONLY_SEQUENCE_SOURCE_REQUIRED")
    name = "_postapp_fixed_" + config["group"]
    if name in sys.modules:
        raise ValueError("FRESH_FIXED_SEQUENCE_NAMESPACE_REQUIRED")
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield from module.sequence(study, config)
    finally:
        if os.getpid() == getattr(study, "postapp_wrapper_owner", os.getpid()):
            pass  # no shared writes or model cleanup in wrapper
