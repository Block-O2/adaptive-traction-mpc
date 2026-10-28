from pathlib import Path
import difflib,json
p=Path('source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py');s=p.read_text();old=s
needle='''            "interval_force_cost_n_s": force_norm * CONTROL_DT_S,
        })
        candidate = _candidate('''
replacement='''            # A boundary proposal owns no interval until execution advances
            # native physics. Rejected admission may revisit this same boundary.
            "interval_force_cost_n_s": 0.0,
            "owned_interval_duration_s": 0.0,
        })
        candidate = _candidate('''
assert s.count(needle)==1;s=s.replace(needle,replacement)
needle='''            executed_interval_count += 1
            if online_timing''';replacement='''            trace[-1]["owned_interval_duration_s"] = execution["actual_interval_duration_s"]
            trace[-1]["interval_force_cost_n_s"] = force_norm * execution["actual_interval_duration_s"]
            executed_interval_count += 1
            if online_timing''';assert s.count(needle)==1;s=s.replace(needle,replacement)
needle='''            attempt = runtime.get("last_execution_attempt", {})
            if attempt.get("applied") or attempt.get("native_steps", 0):''';replacement='''            attempt = runtime.get("last_execution_attempt", {})
            # Preserve failed attempts, crediting only the physical interval
            # actually owned by this attempt (zero for pre-apply rejection).
            owned_dt = max(0.0, float(plant.data.time) - physical_now)
            trace[-1]["owned_interval_duration_s"] = owned_dt
            trace[-1]["interval_force_cost_n_s"] = force_norm * owned_dt
            if attempt.get("applied") or attempt.get("native_steps", 0):''';assert s.count(needle)==1;s=s.replace(needle,replacement)
# Moment reduction used an execution count as a row bound; duplicate rejected
# boundaries must not cause the last real interval to be dropped.
needle='for index in range(min(executed_interval_count, max(0, len(task_rows) - 1)))';assert s.count(needle)==1;s=s.replace(needle,'for index in range(max(0, len(task_rows) - 1))')
p.write_text(s);Path('audit/REPAIR.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='baseline/'+str(p),tofile='repair/'+str(p))))
print(Path('audit/REPAIR.patch').read_text())
