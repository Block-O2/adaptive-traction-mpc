"""Pure proposed scalar -> existing old18d/T intent mapping. No IO or physics.

Parameter-domain legality does not grant scheduler feasibility, actual execution,
motion qualification or safety. Lambda zero is explicitly NOT original B.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _validate_sources(frozen18d, parameter_map, h150):
    vector = frozen18d.get("free_parameters")
    rows = parameter_map.get("parameters")
    if not isinstance(vector,list) or len(vector) != 18 or not all(finite(v) for v in vector):
        raise ValueError("FROZEN_18D_VECTOR_REQUIRED")
    if not isinstance(rows,list) or len(rows) != 18:
        raise ValueError("EXACT_18_PARAMETER_MAP_REQUIRED")
    for index,(value,row) in enumerate(zip(vector,rows)):
        if row.get("index_zero_based") != index or row.get("normalized_bounds") != [-1,1]:
            raise ValueError("EXPECTED_SYMMETRIC_ORIGINAL_PARAMETER_BOX")
        scale = row.get("scale")
        if not finite(scale) or scale <= 0 or abs(value) > scale or row.get("value") != value:
            raise ValueError("FROZEN_PARAMETER_OR_SCALE_OUTSIDE_ORIGINAL_BOX")
    if parameter_map.get("additional_frozen_native_residuals") != frozen18d.get("phases"):
        raise ValueError("ADDITIONAL_NATIVE_RESIDUAL_IDENTITY")
    allowed = {"id","base","posture","early","timing","changes","candidate_hash"}
    if not isinstance(h150,dict) or h150.get("base") != "T" or set(h150)-allowed:
        raise ValueError("ONLY_REVIEWED_T_H150_CANDIDATE_SCHEMA")
    if h150.get("changes") != []:
        raise ValueError("UNSCALED_MULTISEGMENT_CHANGES_NOT_AUTHORIZED")
    for field in ("posture","early","timing"):
        if not isinstance(h150.get(field),list):
            raise ValueError("EXPLICIT_H150_ADJUNCT_LIST_REQUIRED:"+field)
    for intent in h150["posture"]:
        if set(intent) != {"phase","slot","delta_deg"} or intent["phase"] != "RETURN" or not isinstance(intent["slot"],int):
            raise ValueError("UNKNOWN_POSTURE_INTENT")
        delta = intent["delta_deg"]
        if not isinstance(delta,list) or len(delta) != 2 or not all(finite(v) and abs(v) <= .3 for v in delta):
            raise ValueError("POSTURE_NOT_IN_ORIGINAL_POINT3_DEG_BOX")
    for field,lower,upper in (("early",1.0,1.30),("timing",.75,1.50)):
        for intent in h150[field]:
            if set(intent) != {"phase","slot","duration_factor"} or intent["phase"] != "RETURN" or not isinstance(intent["slot"],int):
                raise ValueError("UNKNOWN_DURATION_INTENT:"+field)
            if field == "timing" and intent["slot"] != 5:
                raise ValueError("TIMING_ONLY_ORIGINAL_RETURN5")
            factor = intent["duration_factor"]
            if not finite(factor) or not lower <= factor <= upper:
                raise ValueError("DURATION_FACTOR_OUTSIDE_ORIGINAL_BOX:"+field)
    return vector,rows


def make_axis_contract(frozen18d, parameter_map, h150_candidate, *, source_files_sha256):
    """Construct proposed immutable contract; caller freezes actual file hashes.

    The contract embeds every source object, so later action mapping validates
    actual embedded content rather than trusting self-declared action hashes.
    The source closure must include the worker/control/planners plus FROZEN_18D
    and PARAMETER_MAP. The main runner independently checks the actual files.
    """
    _validate_sources(frozen18d,parameter_map,h150_candidate)
    required = {"runtime/FROZEN_18D.json","runtime/PARAMETER_MAP.json","source/v8_worker_v1.py",
                "runtime/control/campaign_v6.py","runtime/control/base_campaign.py",
                "runtime/code/rich_planner.py","runtime/code/terminal_repair.py",
                "runtime/control/round_planner.py","runtime/control/early_return_planner.py",
                "runtime/control/terminal_planner.py"}
    if not required <= set(source_files_sha256) or any(not isinstance(h,str) or len(h)!=64 for h in source_files_sha256.values()):
        raise ValueError("FULL_SCALING_SOURCE_CLOSURE_NOT_BOUND")
    return {"schema":"v8.old18d_h150_continuous_scale_axis.v1","lambda_domain":[0.0,1.0],
            "frozen18d":copy.deepcopy(frozen18d),"parameter_map":copy.deepcopy(parameter_map),
            "h150_candidate":copy.deepcopy(h150_candidate),"source_files_sha256":dict(source_files_sha256),
            "frozen18d_object_sha256":digest(frozen18d),"parameter_map_object_sha256":digest(parameter_map),
            "h150_candidate_object_sha256":digest(h150_candidate),
            "native_residual_plateaus_scaled":False,"outbound_terminal_repair_factor_scaled":False,
            "zero_intent_entries_removed":False,"legacy_perturbation":[0.0,0.0],
            "lambda_zero_is_original_B":False,"activation":"OUT0_NO_ORIGINAL_B_DELAY",
            "original_qualification_granted":False,"status":"PROPOSED_NOT_PHYSICALLY_COMMISSIONED"}


def validate_axis(axis, expected_axis_sha256):
    if digest(axis) != expected_axis_sha256 or axis.get("schema") != "v8.old18d_h150_continuous_scale_axis.v1":
        raise ValueError("FROZEN_AXIS_ACTUAL_CONTENT_IDENTITY")
    for key,hashkey in (("frozen18d","frozen18d_object_sha256"),("parameter_map","parameter_map_object_sha256"),("h150_candidate","h150_candidate_object_sha256")):
        if digest(axis[key]) != axis[hashkey]:
            raise ValueError("EMBEDDED_SOURCE_OBJECT_CHANGED:"+key)
    if axis.get("lambda_zero_is_original_B") is not False or axis.get("native_residual_plateaus_scaled") is not False or axis.get("outbound_terminal_repair_factor_scaled") is not False or axis.get("zero_intent_entries_removed") is not False:
        raise ValueError("RETAINED_T_OR_NATIVE_RESIDUAL_SEMANTICS_CHANGED")
    return _validate_sources(axis["frozen18d"],axis["parameter_map"],axis["h150_candidate"])


def map_lambda(axis, lambda_value, *, expected_axis_sha256):
    vector,rows = validate_axis(axis,expected_axis_sha256)
    if not finite(lambda_value) or not 0.0 <= lambda_value <= 1.0:
        raise ValueError("LAMBDA_OUTSIDE_CLOSED_ENGINEERING_DOMAIN_NO_CLIP")
    lam = float(lambda_value)
    parameters = [lam*v for v in vector]
    if any(abs(v)>r["scale"] for v,r in zip(parameters,rows)):
        raise ValueError("SCALED_PARAMETERS_OUTSIDE_ORIGINAL_BOX")
    template = axis["h150_candidate"]
    posture = [{**copy.deepcopy(intent),"delta_deg":[lam*v for v in intent["delta_deg"]]} for intent in template["posture"]]
    durations = {field:[{**copy.deepcopy(intent),"duration_factor":1.0+lam*(intent["duration_factor"]-1.0)} for intent in template[field]] for field in ("early","timing")}
    # Keep entries even at lambda=0: unit-factor and zero-posture intents still
    # run original checks. Removing them would silently change planner semantics.
    candidate = {"base":"T","posture":posture,"early":durations["early"],"timing":durations["timing"],"changes":[]}
    candidate["candidate_hash"] = digest(candidate)
    overrides = {k:copy.deepcopy(v) for k,v in candidate.items() if k != "base"}
    action = {"family":"old18d","parameters":parameters,"legacy":[0.0,0.0],"candidate_overrides":overrides}
    recipe = {"axis_contract_sha256":expected_axis_sha256,"lambda":lam,"action":action,
              "resolved_base_candidate":candidate,"source_files_sha256":dict(axis["source_files_sha256"]),
              "retained_native_residuals_object_sha256":digest(axis["frozen18d"]["phases"]),
              "outbound_terminal_repair_factor":1.5,"zero_intent_entries_retained":True,
              "lambda_zero_is_original_B":False,"original_qualification_granted":False}
    return {"lambda":lam,"proposal_action":action,"full_recipe":recipe,"full_recipe_sha256":digest(recipe),
            "physical_action_sha256":digest(action),"axis_contract_sha256":expected_axis_sha256,
            "parameter_box_valid":True,"physical_execution_validated":False}
