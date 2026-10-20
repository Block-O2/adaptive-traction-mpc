# Adversarial command probes

44 reference-and-certification probes across two tasks and two phases. Status counts: {'IDENTICAL_CONTINUATION': 4, 'ACCEPTED': 30, 'REJECTED_CONTINUE_CERTIFIED': 6, 'MISSING_CONTINUE_CERTIFIED': 4}.

| case | phase | test | status | reason / activation |
| --- | --- | --- | --- | --- |
| sync_120 | OUTBOUND | identical | IDENTICAL_CONTINUATION | 0.02 |
| sync_120 | OUTBOUND | small_forward | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | larger_forward | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | reverse | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | alternating | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | hip_to_knee_switch | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | outside_short_horizon | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | near_ROM | ACCEPTED | 0.02 |
| sync_120 | OUTBOUND | outside_ROM | REJECTED_CONTINUE_CERTIFIED | TARGET_OUTSIDE_ROM |
| sync_120 | OUTBOUND | late | ACCEPTED | 0.03 |
| sync_120 | OUTBOUND | missing | MISSING_CONTINUE_CERTIFIED | retained |
| sync_120 | RETURN | identical | IDENTICAL_CONTINUATION | 0.02 |
| sync_120 | RETURN | small_forward | ACCEPTED | 0.02 |
| sync_120 | RETURN | larger_forward | ACCEPTED | 0.02 |
| sync_120 | RETURN | reverse | ACCEPTED | 0.02 |
| sync_120 | RETURN | alternating | ACCEPTED | 0.02 |
| sync_120 | RETURN | hip_to_knee_switch | ACCEPTED | 0.02 |
| sync_120 | RETURN | outside_short_horizon | ACCEPTED | 0.02 |
| sync_120 | RETURN | near_ROM | ACCEPTED | 0.02 |
| sync_120 | RETURN | outside_ROM | REJECTED_CONTINUE_CERTIFIED | TARGET_OUTSIDE_ROM |
| sync_120 | RETURN | late | ACCEPTED | 0.03 |
| sync_120 | RETURN | missing | MISSING_CONTINUE_CERTIFIED | retained |
| low_ordinary_early | OUTBOUND | identical | IDENTICAL_CONTINUATION | 0.02 |
| low_ordinary_early | OUTBOUND | small_forward | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | larger_forward | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | reverse | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | alternating | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | hip_to_knee_switch | REJECTED_CONTINUE_CERTIFIED | FULL_CONTINUATION_CERTIFICATION_REJECTED |
| low_ordinary_early | OUTBOUND | outside_short_horizon | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | near_ROM | ACCEPTED | 0.02 |
| low_ordinary_early | OUTBOUND | outside_ROM | REJECTED_CONTINUE_CERTIFIED | TARGET_OUTSIDE_ROM |
| low_ordinary_early | OUTBOUND | late | ACCEPTED | 0.03 |
| low_ordinary_early | OUTBOUND | missing | MISSING_CONTINUE_CERTIFIED | retained |
| low_ordinary_early | RETURN | identical | IDENTICAL_CONTINUATION | 0.02 |
| low_ordinary_early | RETURN | small_forward | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | larger_forward | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | reverse | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | alternating | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | hip_to_knee_switch | REJECTED_CONTINUE_CERTIFIED | FULL_CONTINUATION_CERTIFICATION_REJECTED |
| low_ordinary_early | RETURN | outside_short_horizon | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | near_ROM | ACCEPTED | 0.02 |
| low_ordinary_early | RETURN | outside_ROM | REJECTED_CONTINUE_CERTIFIED | TARGET_OUTSIDE_ROM |
| low_ordinary_early | RETURN | late | ACCEPTED | 0.03 |
| low_ordinary_early | RETURN | missing | MISSING_CONTINUE_CERTIFIED | retained |


Outside-ROM requests explicitly reject. The low-ROM hip-to-knee change fails full-continuation certification in both phases and retains its certified path. A far intention beyond the immediately reachable horizon is allowed as a soft target if its complete approach is certified. Near-ROM targets must also satisfy continuous OTG extrema and clearance. Late command received at 20 ms, ready at 27 ms, activates at 30 ms; its 25 ms committed prefix is explicitly checked against the prior path. Missing commands retain a certified stationary-target continuation. No discontinuous replacement is accepted. These finite probes do not guarantee all adversarial inputs or hardware fallback safety.
