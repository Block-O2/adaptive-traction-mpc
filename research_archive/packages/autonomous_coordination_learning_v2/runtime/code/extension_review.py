from extension_common import *

def main():
    replay=json.loads((EXT/'ACTIVATION_REPLAY.json').read_text());backlog=json.loads((EXT/'BACKLOG_AND_RAW_AUDIT.json').read_text())
    print(json.dumps(dict(replay={k:replay[k] for k in ('status','captures','input_capture_failures','captured_final_record_mismatches','existing_C2_output_mismatches')},replay_rows=[{k:r.get(k) for k in ('index','name','phase','feasible','capture_ms','first_elapsed_ms','warm_elapsed_ms','warm_thread_cpu_ms','existing_C2_diagnostic_elapsed_ms','captured_final_record_differences','argument_types')} for r in replay['rows']],backlog_groups=backlog['groups'],new_diagnostic={k:backlog['new_diagnostic'][k] for k in ('error','captures','task_requests','phase_coverage','capture_elapsed_ms','actual_original_with_nested_capture_ms')},raw={k:backlog['new_diagnostic']['raw_provenance'][k] for k in ('status','native_step_count','original_wall_record_physics_elapsed_s','computed_steps_before_actual_write','actual_wall_new_command_steps_on_grid_before_host_write','actual_wall_max_grid_start_lead_ms','issues')},total_native_steps=backlog['authoritative_total_native_steps'])))

if __name__=='__main__':main()
