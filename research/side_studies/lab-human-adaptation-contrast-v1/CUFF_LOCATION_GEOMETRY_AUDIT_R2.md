# R2 cuff geometry audit

Formal rho levels .60/.66/.72; all seven conditions compiled with unchanged truth parameterization. Actual MuJoCo sleeve site and geom centers agree with the lever; verified JSON fields contain the physical arrays. Geometry/path evaluation does not feed truth to controller.

|rho|lever (m)|sleeve interval (m)|initial sleeve/table gap (mm)|full sleeve distal-half proximal margin (mm)|
|---|---:|---|---:|---:|
|0.60|0.2404560|0.2004560–0.2804560|5.953957|0.076000|
|0.66|0.2645016|0.2245016–0.3045016|3.858245|24.121600|
|0.72|0.2885472|0.2485472–0.3285472|1.762533|48.167200|

129 sampled IK poses per unique geometry, 1201-point original rigid-table envelope, valid full sleeve/cuff/bar/adapter, no initial penetrating contacts; mass matrices positive and unchanged identifier/prior bounds contain truth. Original thresholds unchanged. Necessary conditions only; neither dynamic commissioning/TASK nor tolerances proven. Raw [9,27] probe geometry is unsafe literally even nominal, and requires the unchanged validated DEV-D feedback projection. Sleeve collision is disabled, so contact enumeration alone is insufficient; original full-cylinder analytic envelope is retained.

Old rho.77 initial sleeve gap .016106mm and rho.85 penetration −2.778176mm are preserved in CUFF_LOCATION_GEOMETRY_AUDIT.json. Neither is in formal R2 dynamic matrix. Rho.60 full sleeve distal-half margin .076mm is nominal geometry, not a tolerance guarantee.
