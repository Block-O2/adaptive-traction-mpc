# Read-only final checkpoint value/actor audit

Native causal teacher states only; no rollout, learning, imitation, normalization update or buffer write. Alternative raw actions are sampled from the arm's own final online replay at identical teacher states. Q scores are estimates, not physical success.

|Arm|Teacher cohort|N|Teacher Q|Online-action Q|Actor Q|Teacher preferred|Actor action MAE hip/knee|
|---|---|---:|---:|---:|---:|---:|---|
|A|OUTBOUND|272|-31.1840|-29.9257|-24.8217|0.5257|[0.1751074641942978, 1.1280083656311035]|
|A|HOLD|35|247.8601|253.2563|243.8782|0.1714|[0.5787396430969238, 1.82801353931427]|
|A|RETURN|286|-368.3708|-380.3509|-368.2759|0.6469|[1.678821086883545, 0.3496297299861908]|
|A|OUTBOUND_first64|64|115.6177|126.7881|135.2321|0.3438|[0.2595762014389038, 0.6256930828094482]|
|A|OUTBOUND_last64|64|-276.2621|-281.0075|-275.8296|0.7500|[0.2860732674598694, 0.7482929229736328]|
|A|RETURN_last64|64|-876.7871|-875.4151|-860.0945|0.3750|[1.8852664232254028, 0.40474575757980347]|
|B|OUTBOUND|272|-134.3339|-136.6299|-132.2426|0.5735|[0.7966334819793701, 0.806891679763794]|
|B|HOLD|35|308.8519|292.1749|309.2048|1.0000|[0.20375283062458038, 0.01271048467606306]|
|B|RETURN|286|986.0239|791.8171|1002.6110|0.9615|[0.08146673440933228, 0.1409217119216919]|
|B|OUTBOUND_first64|64|-44.8323|-48.0308|-43.4071|0.7656|[0.17285287380218506, 0.5499802827835083]|
|B|OUTBOUND_last64|64|-205.3138|-212.5468|-202.3680|0.6875|[0.05006060376763344, 1.331177830696106]|
|B|RETURN_last64|64|815.5562|639.3287|833.8448|0.9531|[0.08004748821258545, 0.14633020758628845]|

The earliest OUTBOUND and late RETURN cohorts describe the final learned value profile; they cannot by themselves prove how values propagated during learning. Actual training visitation is in PHASE_COVERAGE_COMPARISON.json. Combine these Q estimates with actor discrepancy and saved-trace goal settling evidence; never rank invalid task costs.
