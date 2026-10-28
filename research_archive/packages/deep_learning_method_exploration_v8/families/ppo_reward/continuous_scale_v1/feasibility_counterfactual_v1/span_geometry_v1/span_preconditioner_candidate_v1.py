"""SOURCE_ONLY frozen two-context span geometry, no learner/density APIs."""
import math

GROUPS = ("DEVELOPMENT_HEAVY035", "DEVELOPMENT_LIGHT065")


def dot26(a,b,counts):
    if len(a)!=26 or len(b)!=26: raise ValueError("EXACT_AUGMENTED26_REQUIRED")
    counts["geometry_dot26"] += 1
    return sum(x*y for x,y in zip(a,b))


def norm52(matrix,counts):
    if len(matrix)!=2 or any(len(row)!=26 for row in matrix): raise ValueError("EXACT_TWO_HEAD52_REQUIRED")
    counts["geometry_norm52"] += 1
    result=math.sqrt(sum(v*v for row in matrix for v in row))
    if not math.isfinite(result): raise ValueError("NONFINITE_SPAN_GEOMETRY_NORM")
    return result


def solve2(span,rhs,counts):
    counts["geometry_two_by_two_solves"] += 1
    a,b,c,det=span["HH"],span["HL"],span["LL"],span["det"]
    return [(c*rhs[0]-b*rhs[1])/det,(a*rhs[1]-b*rhs[0])/det]


def prepare_frozen_span(rows,source,gatek,counts):
    z={};norm=source["normalization"]
    for group in GROUPS:
        pair=[row for row in rows if row["original_context_label"]==group]
        if len(pair)!=2 or pair[0]["commissioned25"]!=pair[1]["commissioned25"]:
            raise ValueError("EXACT_FROZEN_TWO_DRAW_CONTEXT_BASIS_REQUIRED")
        if len(norm["mean"])!=25 or len(norm["scale"])!=25 or any(not math.isfinite(s) or s<=0 for s in norm["scale"]):
            raise ValueError("ORIGINAL_POSITIVE_TRAIN_ONLY_NORMALIZATION")
        z[group]=[1.0]+[(v-m)/s for v,m,s in zip(pair[0]["commissioned25"],norm["mean"],norm["scale"])]
        counts["geometry_normalized_scalar_features"] += 25
    h,l=GROUPS; a,b,c=dot26(z[h],z[h],counts),dot26(z[h],z[l],counts),dot26(z[l],z[l],counts)
    det=a*c-b*b
    if not math.isfinite(det) or a<=0 or c<=0 or det/(a*c)<=1e-12:
        raise ValueError("RANK_FAILURE_NO_PSEUDOINVERSE_RIDGE_OR_SCORE_FALLBACK")
    if gatek["augmented_feature_Gram"]!={h:{h:a,l:b},l:{h:b,l:c}}:
        raise ValueError("NEW_NORMALIZATION_OR_CONTEXT_BASIS_FORBIDDEN_EXACT_GATEK_GRAM")
    span={"z":z,"HH":a,"HL":b,"LL":c,"det":det,"relative_determinant":det/(a*c)}
    # Coefficient-space map M=K^-1 D; K M=D, including zero offdiagonals.
    columns=[solve2(span,[a,0.0],counts),solve2(span,[0.0,c],counts)]
    effective=[]
    for i,row in enumerate(([a,b],[b,c])):
        values=[]
        for j,column in enumerate(columns):
            counts["geometry_dot2"] += 1
            value=sum(x*y for x,y in zip(row,column)); expected=(a if i==0 else c) if i==j else 0.0
            counts["geometry_effective_kernel_invariant_checks"] += 1
            if abs(value-expected)>1e-12+1e-9*abs(expected): raise ValueError("FROZEN_EFFECTIVE_KERNEL_NOT_DIAGONAL")
            values.append(value)
        effective.append(values)
    span["coefficient_map_columns"]=columns;span["unrescaled_effective_kernel"]=effective
    return span


def precondition(raw_gradient,context_coefficients,span,counts):
    """g=Z^T c -> Z^T K^-1 D c, unified Frobenius-norm rescale."""
    h,l=GROUPS; z=span["z"]
    # c is accumulated from the already paid API score's intercept coordinate;
    # no extra score evaluation, scalar density formula or Gram inversion fit.
    for head in range(2):
        for j in range(26):
            expected=context_coefficients[h][head]*z[h][j]+context_coefficients[l][head]*z[l][j]
            counts["geometry_raw_span_coordinate_checks"] += 1
            if abs(raw_gradient[head][j]-expected)>1e-12+1e-9*abs(raw_gradient[head][j]):
                raise ValueError("ACTUAL_SCORE_GRADIENT_NOT_REGISTERED_CONTEXT_SPAN")
    unscaled=[]
    for head in range(2):
        q=solve2(span,[span["HH"]*context_coefficients[h][head],span["LL"]*context_coefficients[l][head]],counts)
        unscaled.append([q[0]*z[h][j]+q[1]*z[l][j] for j in range(26)])
        counts["geometry_reconstructed_scalar_coordinates"] += 26
    raw_norm=norm52(raw_gradient,counts);unscaled_norm=norm52(unscaled,counts)
    if raw_norm==0:
        if unscaled_norm!=0: raise ValueError("ZERO_RAW_GRADIENT_MUST_NOT_CREATE_UPDATE")
        rescale=1.0
    else:
        if unscaled_norm==0: raise ValueError("NONZERO_GRADIENT_COLLAPSED_NO_DAMPING_FALLBACK")
        rescale=raw_norm/unscaled_norm
    transformed=[[rescale*v for v in row] for row in unscaled]
    counts["geometry_rescaled_scalar_coordinates"] += 52
    transformed_norm=norm52(transformed,counts)
    counts["geometry_unified_norm_invariant_checks"] += 1
    if abs(transformed_norm-raw_norm)>1e-12+1e-9*raw_norm:
        raise ValueError("UNIFIED_TWO_HEAD_NORM_NOT_PRESERVED")
    effects={}
    for group,diagonal in [(h,span["HH"]),(l,span["LL"])]:
        effects[group]={}
        for head in range(2):
            actual_unscaled=dot26(z[group],unscaled[head],counts)
            actual_scaled=dot26(z[group],transformed[head],counts)
            target=diagonal*context_coefficients[group][head]
            counts["geometry_feature_effect_invariant_checks"] += 2
            if (abs(actual_unscaled-target)>1e-12+1e-9*abs(target) or
                    abs(actual_scaled-rescale*target)>1e-12+1e-9*abs(rescale*target)):
                raise ValueError("TRAIN_CONTEXT_CROSS_KERNEL_NOT_REMOVED")
            effects[group][str(head)]={"unrescaled":actual_unscaled,"rescaled":actual_scaled,"diagonal_target":target}
    counts["geometry_preconditioner_calls"] += 1
    return transformed,{"original_gradient_norm":raw_norm,"unrescaled_preconditioned_norm":unscaled_norm,
                        "unified_rescale":rescale,"rescaled_preconditioned_norm":transformed_norm,
                        "context_coefficients":context_coefficients,"actual_train_context_shape_logit_effects":effects,
                        "scope":"Frozen two-context span only; common norm rescale, no assertion about unseen-context cross-effects or mean-of-trajectory"}
