function updated = dynamic_robust_v1_adaptive_bounded_update( ...
        current, candidate, adaptive)
%DYNAMIC_ROBUST_V1_ADAPTIVE_BOUNDED_UPDATE Componentwise fixed-rate update.

delta=min(max(candidate(:)-current(:),-adaptive.maximum_update_step), ...
    adaptive.maximum_update_step);
updated=min(max(current(:)+delta,adaptive.theta_min),adaptive.theta_max);
end
