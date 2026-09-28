"""Test-only availability gate; never changes planner result or task config."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'stages/stage5_personalized_motion_learning'
sys.path.insert(0,str(STAGE/'scripts/high_rom_v1'))
import run_dev_case

def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--delay-ms',type=int,choices=(-1,0,100,200),required=True)
    a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
    output=Path(remaining[remaining.index('--output')+1])
    injection={'availability_delay_ms':a.delay_ms,'target_rule':'third RETURN pass-through prefetch','seen_return_requests':[], 'target_request':None,'release_events':[]}
    original=run_dev_case.run_executed_case
    def run(*args,**kwargs):
        capture=kwargs['runtime_capture']
        def ready(pending,now_ns):
            request=pending['request']
            if not pending.get('pass_through_prefetch') or pending['phase'].value!='RETURN':return True
            if request.request_id not in injection['seen_return_requests']:
                injection['seen_return_requests'].append(request.request_id)
                if len(injection['seen_return_requests'])==3:injection['target_request']=request.request_id
            if request.request_id!=injection['target_request']:return True
            lifecycle=capture['runtime']['plan_lifecycle'];row=lifecycle.records()[request.request_id]
            finish=row.get('compute_finish_ns')
            if finish is None:return False
            release=finish+int(max(a.delay_ms,0)*1e6)
            if now_ns<release:return False
            if not injection['release_events']:
                injection['release_events'].append(dict(request_id=request.request_id,compute_finish_ns=finish,
                    visible_ns=now_ns,scheduled_release_ns=release,source_capture_ns=request.sensor_capture_ns,
                    source_age_ms=(now_ns-request.sensor_capture_ns)/1e6))
            return True
        if a.delay_ms>=0:capture['future_result_ready']=ready
        return original(*args,**kwargs)
    run_dev_case.run_executed_case=run
    try:run_dev_case.main()
    finally:
        if output.exists():(output/'PLANNER_READINESS_INJECTION.json').write_text(json.dumps(injection,indent=2)+'\n')
if __name__=='__main__':main()
