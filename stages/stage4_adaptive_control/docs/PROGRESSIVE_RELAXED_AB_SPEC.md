# Relaxed-energy exploratory rigid/P1 A/B — new evidence branch

User-authorized exploratory execution only. Preserve prior strict numerical qualification FAIL and previous startup diagnostic stop; neither is relabeled. Registered P1 and every controller/plant/trajectory coefficient are unchanged.

Exactly the same de23ea3 controller stack, suspended_high_rom, nominal High-ROM Human, population model/geometry lock, 140 mm adapter, seed/reference/force contracts, Reference Manager/Safety Filter/BRAKE. Both arms use 0.25 ms, with 20 physics substeps per unchanged 5 ms control tick. Fresh process/state per run.

Order: rigid 40/40, P1 40/40; only after P1 COMPLETE/finite/bounded, rigid 40/80 then P1 40/80; only after a meaningful finite/bounded comparison without safety/pathology termination, rigid 90/120 then P1 90/120. At most six runs; no restart/replay/tuning.

P1: K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad. Exact registered cubic law with fixed coincident rest frames.

Energy R=U-U0+integral(P_R+P_H+D)dt is diagnostic: always log signed and absolute residual, running normalization, residual slope/growth, U, port work and damping loss. No immediate stop for a small startup ratio, including the previous 0.5339%. No numerical qualification is inferred from surviving the new guards.

Stop immediately on warning/nonfinite/constitutive mechanics inconsistency, negative damping/U beyond original roundoff tolerances, or original structural/ROM/safety termination. Gross deformation guards use registered bench emergency values 10 mm / 10 deg. The 3 mm / 1 deg engineering targets are recorded and required for admission to a harder pair; a single target crossing is not labeled numerical pathology.

Persistent growth is evaluated at boundaries of four consecutive nonoverlapping 50 ms windows, including startup. Positive residual increments must each exceed 0.0001 J over three intervals and sum exceed max(0.01 J, 10% of current energy scale) to stop. This deliberately requires both an absolute magnitude and persistence; it is an exploratory watchdog, not a passivity certificate.

Growing amplitude: all three consecutive window ratios >=1.5 and total >=4. Require a material last-window value: force peak >100 N AND robot/Human cuff acceleration peak >100 m/s2 together; OR force oscillation >50 N; OR translation oscillation >1 mm; OR rotation oscillation >0.5 deg. Oscillation amplitude is max vector norm about the window mean. All windows/logs are saved. These watchdog definitions are frozen before execution, with no result-dependent adjustment.

P1 40/40 admission requires original COMPLETE, max translation <=3 mm and max rotation <=1 deg, with no pathology/safety termination. For 40/80, ordinary maximum-duration incompletion remains meaningful; safety termination, NO_SAFE_ACTION or a terminal BRAKE failure closes admission to 90/120. Original force/safety contracts are unchanged. A 0.25 ms controller rollout is not an independently confirmed fine replay; any required numerical confirmation remains unresolved without extra replay authorization.

Read-only reset/preflight and synthetic diagnostic tests only before execution. Preserve raw summaries/traces, actual-dt derivatives, per-run commands/config/model fingerprints, window growth diagnostics and exact process IDs. Report six scheduled rows including NOT_RUN after a stop. No clinical safety or qualified compliant-physics claim. Everything stays uncommitted.
