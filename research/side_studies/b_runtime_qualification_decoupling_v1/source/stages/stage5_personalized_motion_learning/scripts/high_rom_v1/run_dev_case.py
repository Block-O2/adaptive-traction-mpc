"""One monitored High-ROM development case. Never dispatches a campaign loop."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
for relative in ("stages/stage5_personalized_motion_learning/src","stages/stage4_adaptive_control/src","stages/stage3_full3d/src"):
    sys.path.insert(0,str(ROOT/relative))
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case, _jsonable
import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--host-monitor-limit-s',type=float,default=300.0)
    parser.add_argument('--plant-mode',choices=('high_rom','low_rom'),default='high_rom')
    parser.add_argument('--execution-mode',choices=('REALTIME_CHARACTERIZATION','SCIENTIFIC_SIMULATION'),
                        default='REALTIME_CHARACTERIZATION')
    parser.add_argument('--scientific-host-delay-ms',type=float,default=0.0)
    args=parser.parse_args()
    case=json.loads(args.case.read_text())
    if args.plant_mode=='high_rom' and case.get('research_model')!='high_rom_v1':raise ValueError('High-ROM case required')
    if args.plant_mode=='low_rom' and 'research_model' in case:raise ValueError('Original low-ROM case required')
    if not str(Path(runtime.__file__).resolve()).startswith(str(ROOT)):
        raise RuntimeError('runtime import outside High-ROM worktree')
    if args.output.exists():raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    options_path=ROOT/'stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json'
    options=json.loads(options_path.read_text())
    stop=ROOT/'stages/stage5_personalized_motion_learning/docs/high_rom_v1/STOP'
    if stop.exists():raise RuntimeError('HIGH_ROM_USER_STOP')
    started=time.monotonic()
    def stop_check():
        if stop.exists():raise RuntimeError('HIGH_ROM_USER_STOP')
        if time.monotonic()-started>=args.host_monitor_limit_s:
            raise RuntimeError('HIGH_ROM_HOST_MONITOR_CUTOFF_INCOMPLETE')
    capture={'stop_check':stop_check}
    source_relatives = (
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/high_rom_v1.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/fresh_qualification_v1/scenario.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/rigid_table_reference.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/terminal_reference.py',
        'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/monotonic_clearance.py',
        'stages/stage5_personalized_motion_learning/configs/high_rom_v1/stage5_goal_task_120_v1.json',
        'stages/stage5_personalized_motion_learning/configs/full3d_adaptive_integration_v1/development_v1_1.json',
    )
    source_hashes = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_relatives}
    record={'schema':'high_rom_v1_development_case_result','case_key':case['case_key'],
            'source_files_sha256':source_hashes,
            'case_sha256':hashlib.sha256(args.case.read_bytes()).hexdigest(),
            'options_sha256':hashlib.sha256(options_path.read_bytes()).hexdigest(),
            'runtime_sha256':hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest(),
            'runtime_path':str(Path(runtime.__file__).resolve()),
            'command':sys.argv,'category':('high_rom_development_not_qualification' if args.plant_mode=='high_rom' else 'low_rom_same_source_development_regression'),
            'plant_mode':args.plant_mode,
            'execution_mode':args.execution_mode,
            'scientific_host_delay_ms':args.scientific_host_delay_ms,
            'host_monitor_limit_s':args.host_monitor_limit_s}
    try:
        summary=run_executed_case(args.output,qualification_case=case,
            qualification_arm='continual_adaptive',simulate_planning_latency=True,
            formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,
            dev_d_rigid_table_reference=True,autonomous_recovery_options=options,
            task_timeout_s=30.0,runtime_capture=capture,
            execution_mode=args.execution_mode,
            scientific_host_delay_s=args.scientific_host_delay_ms/1000.0)
        record['status']=summary.get('status');record['abort_reason']=summary.get('abort_reason');
        record['task']=summary.get('task');record['timing']=summary.get('timing')
    except BaseException as error:
        record['status']='EXCEPTION';record['abort_reason']=f'{type(error).__name__}:{error}'
        record['traceback']=traceback.format_exc()[-5000:]
    finally:
        record['elapsed_host_s']=time.monotonic()-started
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'HIGH_ROM_CASE_RESULT.json').write_text(json.dumps(_jsonable(record),indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:record.get(k) for k in ('case_key','status','abort_reason','elapsed_host_s')}),flush=True)

if __name__=='__main__':main()
