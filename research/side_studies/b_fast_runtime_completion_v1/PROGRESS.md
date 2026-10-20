SETUP: t0=2026-10-07 05:53:58 UTC, immutable 10-hour cap; 120 initial /240 absolute attempts. No physics dispatched.

2026-10-07 06:06:06 UTC: 000_R3_attribution_host COMPLETE, attempts 1/120; elapsed 0.202h.

2026-10-07 06:08:45 UTC: 001_R3_attribution_corrected COMPLETE, attempts 2/120; elapsed 0.247h.

2026-10-07 06:13:44 UTC: 002_R3_plant_cost COMPLETE, attempts 3/120; elapsed 0.330h.

2026-10-07 06:18:08 UTC: 003_N1_plant_cost COMPLETE, attempts 4/120; elapsed 0.403h.

2026-10-07 06:20:08 UTC: 004_N1_C1_science_nominal COMPLETE, attempts 5/120; elapsed 0.436h.

2026-10-07 06:24:48 UTC: 005_N2_C1_science_nominal COMPLETE, attempts 6/120; elapsed 0.514h.

Checkpoint 2026-10-07 06:28:46 UTC; elapsed 0.580h.
Attribution complete: full actual cycles, saved causal command-preview replay, same-model native cost. N1 faster but full SCI tolerance FAIL; N2 full 116320-step SCI bit-exact PASS. C1 ceil(actual availability) local causal regression PASS. R1 full-input same-tick shadow underway. Next: evaluate R1, exact SO3 interior branch, then causal host ladder. No learning enabled.
Physical attempts including cost runs/startup failures: 7/120; no repeated completed IDs. Resource baseline healthy; CPU accounting added for subsequent 45s samples, early sampling gap disclosed.

2026-10-07 06:37:31 UTC: 006_N2_R1_science_nominal FAILED, attempts 7/120; elapsed 0.726h.

2026-10-07 06:40:14 UTC: 007_N3_plant_cost COMPLETE, attempts 8/120; elapsed 0.771h.

2026-10-07 06:41:55 UTC: 008_N3_C1_science_nominal COMPLETE, attempts 9/120; elapsed 0.799h.

2026-10-07 06:44:14 UTC: 009_N3_C1_host_smoke FAILED, attempts 10/120; elapsed 0.838h.

2026-10-07 06:52:08 UTC: 010_N3_C1b_host_smoke COMPLETE, attempts 11/120; elapsed 0.970h.

2026-10-07 06:59:25 UTC: 011_N3_R2_science_nominal FAILED, attempts 12/120; elapsed 1.091h.

Checkpoint 2026-10-07 07:07:24 UTC; elapsed 1.224h.
N3 full 116320-step SCI bit-exact PASS and plant median 53.36us versus original 135.06us. C1b host 117630 steps with zero command/write causality violations and <250us quantization. Full task safety PASS but R2 HOLD 1.07s and feedback median 10.02ms remain FAIL. R1 full-model key closed: excessive 67ms/key. R2 pure numerical reuse local regression PASS; first SCI capture stopped by a nonpicklable live-clock closure, isolated snapshot fix prepared. Next: R2 SCI and saved full controller replay, then profile-supported exact native soft limits/context transaction reuse. No learning enabled.
Physical attempts including cost runs/startup failures: 13/120; no repeated completed IDs. Resource baseline healthy; CPU accounting added for subsequent 45s samples, early sampling gap disclosed.

2026-10-07 07:07:56 UTC: 012_N3_R2_science_nominal COMPLETE, attempts 13/120; elapsed 1.233h.

2026-10-07 07:12:22 UTC: 013_N4_plant_cost COMPLETE, attempts 14/120; elapsed 1.307h.

2026-10-07 07:14:13 UTC: 014_N4_R2_science_nominal COMPLETE, attempts 15/120; elapsed 1.338h.

2026-10-07 07:16:48 UTC: 015_N4_R2_C1b_host COMPLETE, attempts 16/120; elapsed 1.381h.

2026-10-07 07:19:10 UTC: 016_N4_R2_C2_host COMPLETE, attempts 17/120; elapsed 1.420h.

2026-10-07 07:23:03 UTC: 017_N4_V2_C2_science_nominal COMPLETE, attempts 18/120; elapsed 1.485h.

2026-10-07 07:25:45 UTC: 018_N4_V2_C2_host COMPLETE, attempts 19/120; elapsed 1.530h.

2026-10-07 07:30:30 UTC: 019_N4_V2_C2_science_deviation COMPLETE, attempts 20/120; elapsed 1.609h.

2026-10-07 07:45:33 UTC: 020_N4_V2_W1_C2_science_nominal COMPLETE, attempts 21/120; elapsed 1.860h.

2026-10-07 07:50:47 UTC: 021_N4_V2_W1_D1_C2_science_nominal COMPLETE, attempts 22/120; elapsed 1.947h.

Checkpoint 2026-10-07 07:52:09 UTC; elapsed 1.970h.
N4 exact soft limits reduce plant median to 46.44us. N4/V2 expanded exact vector path + C2 poll deadline passes all frozen service/miss/rolling/backlog checks in host018 (p50 5.009ms, p95 5.623ms, p99 6.742ms); 118405 actual steps have zero causal violations. Full physical task PASS, original R2 remains FAIL (HOLD1.06s, OUT9.3s following fallback). Native004/N1 is negative; R1 full-model key closed; R2 small numerical cache is correct but overhead outweighs benefit. N4/V2 nominal and legal-deviation SCI bit-exact PASS. W1 per-request exact proof reuse decision+proof local PASS and full SCI020 bit-exact PASS. D1 direct immutable atomic TASK IPC local PASS, full SCI021 underway; original planner,100ms/current admission and one live plant unchanged. Next: D1 host, then further phase/receipt ownership optimization if R2 remains. No learning enabled.
Physical attempts including cost runs/startup failures: 22/120; no repeated completed IDs. Resource baseline healthy; CPU accounting added for subsequent 45s samples, early sampling gap disclosed.

2026-10-07 07:54:32 UTC: 022_N4_V2_W1_D1_C2_host COMPLETE, attempts 23/120; elapsed 2.010h.

2026-10-07 08:12:49 UTC: 023_N4_V3_W1_D1_science_nominal COMPLETE, attempts 24/120; elapsed 2.314h.

2026-10-07 08:14:18 UTC: 024_N4_V3_W1_D1_host FAILED, attempts 25/120; elapsed 2.339h.

2026-10-07 08:16:24 UTC: 025_N4_V3_W1_D1_host COMPLETE, attempts 26/120; elapsed 2.374h.

Checkpoint 2026-10-07 08:28:41 UTC; elapsed 2.579h; attempts 27/120.
V3 loaded-context reuse: 408 local mutation/ownership cases PASS, SCI023 all native values bit-exact. Host025 full physics/causality and every service/miss/rolling/backlog check PASS; original R2 remains FAIL (HOLD1.05s). Invalid enum startup024 preserved/counts, corrected025. W2 request-local features/Jacobian cache math PASS but OUT/RETURN overhead closes that branch. N5 same-backend fixed features/Gram validation: 10012 +6136 cases bit-exact/error-equivalent PASS, full TASK saved decision/proof PASS; SCI026 underway. Controller-only N5 p50 2.443ms/p95 2.748ms, outlier max13.231ms; no host qualification inferred. No Q/training. Next N5 host and profile-supported handoff preparation.
Direct IPC queues now about0.2ms; remaining HOLD latency includes original worker~5ms, collection/command construction. Current exact mechanics proof cache hits HOLD; current-state/phase/expiry checks retained. Resources healthy, stable swap72.8MB; no system/power changes. Native N4 binary/source frozen before N5 build.

2026-10-07 08:28:43 UTC: 026_N5_V3_W1_D1_science_nominal COMPLETE, attempts 27/120; elapsed 2.579h.

2026-10-07 08:30:08 UTC: 027_N5_V3_W1_D1_host COMPLETE, attempts 28/120; elapsed 2.603h.

2026-10-07 08:42:47 UTC: 028_N5_V3_A1_D1_science_nominal COMPLETE, attempts 29/120; elapsed 2.814h.

2026-10-07 08:46:30 UTC: 029_N5_V3_A1_D1_host COMPLETE, attempts 30/120; elapsed 2.876h.

Checkpoint 2026-10-07 08:54:26 UTC; elapsed 3.008h; attempts 31/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
New C1c receipt metadata preserves offline actual write, original command validation model and committed robot reference pose/twist, with mutation regression PASS. SCI030 plus fuller HOLD/RETURN/controller/admission causal input capture underway. Next: saved actual admission budget and versioned phase/receipt optimization; one live plant, unchanged planner/control/100ms/source/safety/R2. N4/N5 binaries frozen. Resource healthy, swap72.8MB stable; no system/power/Git changes.

2026-10-07 08:54:33 UTC: 030_N5_V3_A1_C1c_science_nominal COMPLETE, attempts 31/120; elapsed 3.010h.

2026-10-07 09:06:06 UTC: 031_N5_V3_A1_C1c_attribution_host COMPLETE, attempts 32/120; elapsed 3.202h.

Checkpoint 2026-10-07 09:16:45 UTC; elapsed 3.380h; attempts 32/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030 C1c/full HOLD and RETURN causal capture bit-exact. Host031 attribution complete: full physical/current admission/causal PASS, R2 HOLD1.045 FAIL, instrumentation rolling service FAIL; attribution only, never qualification. 5546 complete same-cycle intervals: mean feedback1.927ms/native1.027ms/sensor0.533ms/receipt0.332ms/unwrapped1.433ms, wait and minor categories separately in raw closing partitions. Saved original HOLD worker ~3.5-3.8ms, current admission~0.55-0.65ms. GEO1 complete geometry reuse 140 actual input calls +1680 mutations bit-exact but low hit rate/overhead, preserved and closed. N6 fixed margins/J/regressor:27205 local bit-exact cases and6 TASK decisions/proofs PASS; complete SCI032 next. Fake-clock resource recovery5/10/20min and60min/cutoff/disk tests PASS, no real wait or state changes. No Q/training, one live plant, unchanged planner/control/100ms/source/safety/R2. Next: N6 SCI then host, phase scheduling still principal blocker.

2026-10-07 09:18:18 UTC: 032_N6_V3_A1_C1c_science_nominal COMPLETE, attempts 33/120; elapsed 3.406h.

2026-10-07 09:20:42 UTC: 033_N6_V3_A1_C1c_host COMPLETE, attempts 34/120; elapsed 3.446h.

2026-10-07 09:30:27 UTC: 034_N8_V3_A1_C1c_science_nominal COMPLETE, attempts 35/120; elapsed 3.608h.

2026-10-07 09:32:35 UTC: 035_N8_V3_A1_C1c_host COMPLETE, attempts 36/120; elapsed 3.644h.

2026-10-07 09:39:05 UTC: 036_N9_V3_A1_C1c_science_nominal COMPLETE, attempts 37/120; elapsed 3.752h.

2026-10-07 09:41:04 UTC: 037_N9_V3_A1_C1c_host COMPLETE, attempts 38/120; elapsed 3.785h.

Checkpoint 2026-10-07 09:49:53 UTC; elapsed 3.932h; attempts 38/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.

2026-10-07 09:51:28 UTC: 038_N9_C1d_science_nominal COMPLETE, attempts 39/120; elapsed 3.959h.

2026-10-07 09:54:10 UTC: 039_N9_C1d_host COMPLETE, attempts 40/120; elapsed 4.003h.

2026-10-07 10:02:50 UTC: 040_N11_single_step_local COMPLETE, attempts 41/120; elapsed 4.148h.

Checkpoint 2026-10-07 10:03:43 UTC; elapsed 4.163h; attempts 41/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.

2026-10-07 10:05:12 UTC: 041_N11_C1d_science_nominal COMPLETE, attempts 42/120; elapsed 4.187h.

2026-10-07 10:08:14 UTC: 042_N11_C1d_host COMPLETE, attempts 43/120; elapsed 4.238h.

2026-10-07 10:18:36 UTC: 043_N12_C1d_science_nominal COMPLETE, attempts 44/120; elapsed 4.411h.

2026-10-07 10:20:47 UTC: 044_N12_C1d_host COMPLETE, attempts 45/120; elapsed 4.447h.

Checkpoint 2026-10-07 10:27:45 UTC; elapsed 4.563h; attempts 45/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

2026-10-07 10:32:17 UTC: 045_N12_C2b_front_attribution COMPLETE, attempts 46/120; elapsed 4.639h.

2026-10-07 10:45:09 UTC: 046_N13_C2b_science_nominal COMPLETE, attempts 47/120; elapsed 4.853h.

2026-10-07 10:50:03 UTC: 047_N13_C2b_host FAILED, attempts 48/120; elapsed 4.935h.

2026-10-07 10:52:14 UTC: 048_N13_C2b_host COMPLETE, attempts 49/120; elapsed 4.971h.

Checkpoint 2026-10-07 10:53:58 UTC; elapsed 5.000h; attempts 49/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

2026-10-07 10:57:59 UTC: 049_N13_C3_science_nominal COMPLETE, attempts 50/120; elapsed 5.067h.

N13 local3536 bool type/value/truth cases, saved-controller110+10 inputs and all6 TASK decisions/proofs PASS; SCI046 bit-exact. N13a noncanonical NumPy Bool scalar truth negative binary/source preserved. Host047 invalid execution enum startup failure0 physics counted. Corrected host048 physical/current/causal/all service PASS, HOLD1.035 originalR2FAIL. C3 nonblocking completed-TASK extra real service13 local guards PASS, SCI049 bit-exact; protocol frozen beforehost050; samefunctional limits/population. Q OFF.

2026-10-07 11:00:45 UTC: 050_N13_C3_host COMPLETE, attempts 51/120; elapsed 5.113h.

2026-10-07 11:05:35 UTC: 051_N13_C3b_science_nominal COMPLETE, attempts 52/120; elapsed 5.194h.

2026-10-07 11:08:18 UTC: 052_N13_C3b_host COMPLETE, attempts 53/120; elapsed 5.239h.

SCI049 C3 and SCI051 C3b bit-exact. Hosts050/052 physical/current/causal/allservice PASS but HOLD originalR2FAIL; C3 extra completed message services did not remove HOLD bottleneck. N13/C2b diagnostic candidate frozen for4 fresh cold+4 same-interpreter full tasks with new independent seeds, unchanged frozenfunctional/strict/physical/R2 labels. Reused interpreter still new plant, not continuous physical adaptation. Cross-shape saved-input attribution only~.08ms/input unsupportedpath opportunity: no further microtranslation. No BEST or M2 yet.

Checkpoint 2026-10-07 11:13:09 UTC; elapsed 5.320h; attempts 54/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

2026-10-07 11:14:23 UTC: 053_N13_C2b_COLD4_1 COMPLETE; cohort N13_C2b_COLD4; attempts 54/120; interpreter 154532, ordinal 0.

2026-10-07 11:15:49 UTC: 054_N13_C2b_COLD4_2 COMPLETE; cohort N13_C2b_COLD4; attempts 55/120; interpreter 154616, ordinal 0.

2026-10-07 11:17:17 UTC: 055_N13_C2b_COLD4_3 COMPLETE; cohort N13_C2b_COLD4; attempts 56/120; interpreter 154689, ordinal 0.

2026-10-07 11:18:43 UTC: 056_N13_C2b_COLD4_4 COMPLETE; cohort N13_C2b_COLD4; attempts 57/120; interpreter 154783, ordinal 0.

2026-10-07 11:20:53 UTC: 057_N13_C2b_REUSE4_1 COMPLETE; cohort N13_C2b_REUSE4; attempts 58/120; interpreter 154900, ordinal 0.

2026-10-07 11:20:57 UTC: 058_N13_C2b_REUSE4_2 FAILED; cohort N13_C2b_REUSE4; attempts 59/120; interpreter 154900, ordinal 1.

Checkpoint 2026-10-07 11:27:01 UTC; elapsed 5.551h; attempts 59/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

COLD4 all full physical/current/causal PASS, allHOLD R2FAIL; fourth rolling1s max6.068ms >frozen6msFAIL. OriginalREUSE4 first full task then058 serializer repeat-install failed0physics; no unchanged retries, oldcode/result retained. S1 installs original streaming serializer once and restores base function instead of prior-run closure;5localcasesPASS, fullSCI059 pending. W3 complete-model/torque/q allocation reuse3012 localcases and all6 saveddecision/proof/randomized pairs bit-exact with same14280 modelAPIcalls; HOLD slower.096/.211ms andmovingworkers slower7–8ms: closedlocal-only, notenabled onplant. New S1 reused-interpreter4run queue frozen, originalfailures unchanged.

2026-10-07 11:29:24 UTC: 059_N13_S1_science_nominal COMPLETE, attempts 60/120; elapsed 5.591h.

2026-10-07 11:33:33 UTC: 060_N13_S1_REUSE4_1 COMPLETE; cohort N13_S1_REUSE4; attempts 61/120; interpreter 155323, ordinal 0.

2026-10-07 11:34:56 UTC: 061_N13_S1_REUSE4_2 FAILED; cohort N13_S1_REUSE4; attempts 62/120; interpreter 155323, ordinal 1.

SCI059 S1 bit-exact. REUSE S1 run060 fulltask complete;061 fullphysics advanced but post-physicsmode-metadata repeated inspect of dynamicfunction failed; retainedactualsteps/mainAPIdelta and noqualificationrelabel. S2 modepatch now installs once and checks exact auditowneridentity;7localcasesPASS. Added finite commissioning-owner original API delta counters for subsequent evidence; prior worker counters retain disclosed gaps. Optional boundedfault adapter7localcasesPASS, originalrequest3 commissioning andTASK6/packet1 separated; nofaultenabledonSCI062. S2 fullSCI and reusability4run queue registered. QOFF.

2026-10-07 11:40:48 UTC: 062_N13_S2_science_nominal COMPLETE, attempts 63/120; elapsed 5.781h.

2026-10-07 11:43:30 UTC: 063_N13_S2_REUSE4_1 COMPLETE; cohort N13_S2_REUSE4; attempts 64/120; interpreter 155684, ordinal 0.

2026-10-07 11:44:56 UTC: 064_N13_S2_REUSE4_2 COMPLETE; cohort N13_S2_REUSE4; attempts 65/120; interpreter 155684, ordinal 1.

2026-10-07 11:46:21 UTC: 065_N13_S2_REUSE4_3 COMPLETE; cohort N13_S2_REUSE4; attempts 66/120; interpreter 155684, ordinal 2.

Checkpoint 2026-10-07 11:47:03 UTC; elapsed 5.885h; attempts 67/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

2026-10-07 11:47:48 UTC: 066_N13_S2_REUSE4_4 COMPLETE; cohort N13_S2_REUSE4; attempts 67/120; interpreter 155684, ordinal 3.

2026-10-07 11:50:09 UTC: 067_N13_S2_science_deviation COMPLETE, attempts 68/120; elapsed 5.936h.

2026-10-07 11:55:48 UTC: 068_N13_S2_legal_host COMPLETE, attempts 69/120; elapsed 6.031h.

Checkpoint 2026-10-07 11:56:49 UTC; elapsed 6.048h; attempts 70/120.
N5 original fixed-feature/Gram kernels: 10012+6136 local cases PASS, SCI026 bit-exact. Host027 first TASK submit stalled238.8ms in main input envelope/send section; original source-age check stopped without meaningful task activation. Preserved, no threshold relaxed. D1 submission now logs serialize/send wall and thread CPU plus GC state. RAW_A1 keys remove expensive canonical JSON expansion, all422 mutation cases and saved TASK decision/proof PASS. A1a false misses from pickle aliasing preserved; memo-free A1b fixes equal-value identity. SCI028 bit-exact. Host029 full physical/current admission/causal and all service/rolling/backlog checks PASS; R2 remains FAIL solely HOLD1.05s. OUT9.01/RETURN9.0075; 117330 actual steps; no expired writes or missing model/reference versions. No Q/training.
SCI030/032/034/036 bit-exact full trajectories. Host031 attribution:5546 whole actual cycles mean feedback1.927/native1.027/sensor0.533/receipt0.332/unwrapped1.433/wait0.031/current-admission0.0026/snapshot0.00084ms; sums close actual whole cycles. Host033 N6 full physical/current admission/causal and all service gates PASS, HOLD1.035s R2FAIL. Host035 N8 HOLD1.040, host037 N9 HOLD1.045; service gates allPASS, host037 agep5044.75/max57.24ms,11 meaningful plans. No R2-qualified B/BEST/M2. N6 local27205, N8 complete-value-tree6070, N9 quintic40009 cases bit-exact plus original TASK/proof checks. GEO1 complete geometry reuse1680 mutations correct but slower; closed. N7 observer2400 bit-exact ~3us median gain, N10 outer mechanics150+300 accept/reject bit-exact with unchanged21 API calls ~0.10ms gain: both local-only closed and binaries preserved. Next C1d defers old-control receipt preparation integration until true availability; original pure ZOH reference guard at same original readiness grid, no observer/state/phase projection.27 fake-clock guard/write/old-interval cases PASS; full SCI038 then host if PASS. Fake-clock resource5/10/20m,60m/cutoff/disk guards PASS. No power/system/Git/Q changes.
Update: SCI038 PASS bit-exact. Host039 C1d full OUT/HOLD/RETURN, physical/current admission/causal/all service checks PASS; HOLD1.040 R2FAIL, OUT9.010/RETURN9.01125;117205 steps,12 meaningful plans,agep5045.017/max55.102ms,servicep504.996/p955.478/p996.266/max33.356ms,backlogmax.013499s. C1d reduces prewrite construction but original hold handoff remains binding. N11 exactly one original step/refresh sequence consolidates Python boundaries; local040 two identical hidden plants original validated constant support3000 paired steps/6000 actual steps/36000 array comparisons, interface/cache/history bit-exact; same-test native median33.973us versus42.159us. Scientific full regression pending; no qualification claim from local kernel speed.
Update: SCI041 N11 and SCI043 N12 full original trajectories bit-exact. Host042 and044 full physical/current/causal/service PASS, both HOLD1.035 R2FAIL;042 age max53.824/044 max52.230ms all actual plans under55. Pending feedback audit042 proves fresh source, changed torque, moving reference during pending plans plus commissioning/recovery services; offline actual write and actualTRACK poses complete. N12 5004 outward-interval local cases bit-exact, all6 saved original TASK decisions/proofs equal; randomized same-interpreter50 HOLD pairs median saving.186/.209ms,21 original model calls preserved. Native binaries N11/N12 frozen. C1d additional12 expiry/lifecycle fake boundaries PASS. Preparing C2b telemetry repair: previous C2 overwrote multirate next-tick telemetry, so service_compute included wait/catch-up; preserve old rows, new version marks real pre-wait owner work separately. Resource60m closeout latch fixed (never actually triggered). Q remains OFF; no R2-qualified BEST.

2026-10-07 11:57:18 UTC: 069_N13_S2_legal_host COMPLETE, attempts 70/120; elapsed 6.056h.

2026-10-07 11:59:21 UTC: 070_COMMISSIONING_worker_delay COMPLETE, attempts 71/120; elapsed 6.090h.

2026-10-07 11:59:39 UTC: 071_COMMISSIONING_expired_result FAILED, attempts 72/120; elapsed 6.095h.

2026-10-07 11:59:56 UTC: 072_COMMISSIONING_explicit_native_rejection FAILED, attempts 73/120; elapsed 6.100h.

2026-10-07 12:01:23 UTC: 073_TASK_worker_delay COMPLETE, attempts 74/120; elapsed 6.124h.

2026-10-07 12:02:51 UTC: 074_TASK_expired_result COMPLETE, attempts 75/120; elapsed 6.148h.

2026-10-07 12:04:20 UTC: 075_TASK_model_version_mismatch COMPLETE, attempts 76/120; elapsed 6.173h.

2026-10-07 12:04:56 UTC: 076_TASK_explicit_native_rejection COMPLETE, attempts 77/120; elapsed 6.183h.

2026-10-07 12:07:15 UTC: 077_N13_S2_C4_science_nominal COMPLETE, attempts 78/120; elapsed 6.221h.

2026-10-07 12:09:42 UTC: 078_N13_S2_C4_host_nominal COMPLETE, attempts 79/120; elapsed 6.262h.

2026-10-07 12:13:04 UTC: 080_N13_S2_C4_science_deviation COMPLETE, attempts 80/120; elapsed 6.319h.

2026-10-07 12:16:18 UTC: 079_N13_S2_C4_host_deviation COMPLETE, attempts 81/120; elapsed 6.372h.

2026-10-07 12:22:23 UTC: 081_N13_S2_C5_science_nominal COMPLETE, attempts 82/120; elapsed 6.474h.

2026-10-07 12:22:31 UTC checkpoint: elapsed6.476h, attempts82/120. Four cold and four repaired same-interpreter runs plus two legal hosts complete physical/causal/service but all R2 HOLD failures preserved. Seven bounded faults executed; commissioning expiry/rejection stop, TASK expiry retries using original authority, identity mismatch rescreens, TASK explicit rejection terminates (export COMPLETE is not task success). C4 nominal/deviation scientific bit-exact and host physical/causal/service PASS but R2 FAIL; C5 original committed endpoint notification now under scientific regression. No qualified BEST/M2/Q/training.

2026-10-07 12:25:11 UTC: 082_N13_S2_C5_host_nominal COMPLETE, attempts 83/120; elapsed 6.520h.

2026-10-07 12:30:38 UTC: 085_TASK7_moving_worker_delay COMPLETE, attempts 84/120; elapsed 6.611h.

2026-10-07 12:39:17 UTC: 091_N13_S2_D2_science_nominal COMPLETE, attempts 85/120; elapsed 6.756h.

2026-10-07 12:41:24 UTC: 087_N13_S2_C5b_science_nominal COMPLETE, attempts 86/120; elapsed 6.791h.

2026-10-07 12:46:13 UTC: 088_N13_S2_C5b_host_nominal COMPLETE, attempts 87/120; elapsed 6.871h.

2026-10-07 12:46:41 UTC checkpoint: elapsed6.879h, attempts87/120. Four cold and four repaired same-interpreter runs plus two legal hosts complete physical/causal/service but all R2 HOLD failures preserved. Seven bounded faults executed; commissioning expiry/rejection stop, TASK expiry retries using original authority, identity mismatch rescreens, TASK explicit rejection terminates (export COMPLETE is not task success). C4 nominal/deviation scientific bit-exact and host physical/causal/service PASS but R2 FAIL; C5 original committed endpoint notification now under scientific regression. No qualified BEST/M2/Q/training.

2026-10-07 12:54:14 UTC: 092_N13_S2_D2_TASK7_worker_delay COMPLETE, attempts 88/120; elapsed 7.004h.

2026-10-07 13:01:01 UTC: 093_N13_S2_D2_TASK7_expired_result COMPLETE, attempts 89/120; elapsed 7.118h.

2026-10-07 13:16:15 UTC: 094_N13_S2_D2_C5c_science_nominal COMPLETE, attempts 90/120; elapsed 7.372h.

2026-10-07 13:18:12 UTC: 095_N13_S2_D2_C5c_host_nominal COMPLETE, attempts 91/120; elapsed 7.404h.

2026-10-07 13:18:35 UTC checkpoint: elapsed7.410h, attempts91/120. Four cold and four repaired same-interpreter runs plus two legal hosts complete physical/causal/service but all R2 HOLD failures preserved. Seven bounded faults executed; commissioning expiry/rejection stop, TASK expiry retries using original authority, identity mismatch rescreens, TASK explicit rejection terminates (export COMPLETE is not task success). C4 nominal/deviation scientific bit-exact and host physical/causal/service PASS but R2 FAIL; C5 original committed endpoint notification now under scientific regression. No qualified BEST/M2/Q/training.

2026-10-07 13:25:16 UTC: 098_N13_S2_D2_C6_science_nominal COMPLETE, attempts 92/120; elapsed 7.522h.

2026-10-07 13:27:41 UTC: 099_N13_S2_D2_C6_host_nominal COMPLETE, attempts 93/120; elapsed 7.562h.

2026-10-07 13:30:26 UTC: 100_N13_S2_D2_C6_science_deviation COMPLETE, attempts 94/120; elapsed 7.608h.

2026-10-07 13:32:52 UTC: 101_N13_S2_D2_C6_host_deviation COMPLETE, attempts 95/120; elapsed 7.649h.

2026-10-07 13:46:39 UTC: 102_N13_S2_D2_C6_handoff_science COMPLETE, attempts 96/120; elapsed 7.878h.

2026-10-07 13:48:49 UTC: 103_N13_S2_D2_C6_handoff_host COMPLETE, attempts 97/120; elapsed 7.914h.
