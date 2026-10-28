"""No-physics adversarial budget/resource admission tests in a shadow ledger."""
from pathlib import Path
import json,sys,tempfile,time
import research_common as campaign
from research_common import ROOT,atomic,now
sys.path.insert(0,str(campaign.RUNTIME))
from resource_guard import Guard,ResourceStop

def main():
    out=ROOT/'audit/BUDGET_GUARD_TEST';out.mkdir(exist_ok=False)
    rows=[];real_root=campaign.ROOT;real_deadline=campaign.HARD_STOP
    def rejects(name,fn,expected):
        try:fn()
        except (RuntimeError,ResourceStop) as exc:
            ok=expected in str(exc);rows.append(dict(test=name,pass_=ok,observed=str(exc)));assert ok
        else:raise AssertionError(name+' unexpectedly admitted')
    def write_ledger(**changes):
        x=dict(attempts=[],native_steps=0,training_attempts=0,evaluation_attempts=0,
               optimizer_steps=0,rl_decisions=0,gradient_train_calls=0)
        x.update(changes);atomic(out/'LEDGER.json',x)
    try:
        campaign.ROOT=out
        write_ledger(training_attempts=450)
        rejects('450_training_hard_cap',lambda:campaign.reserve('training','test',out/'none',1),'ATTEMPT_HARD_CAP')
        write_ledger(evaluation_attempts=60)
        rejects('60_evaluation_hard_cap',lambda:campaign.reserve('evaluation','test',out/'none',1),'ATTEMPT_HARD_CAP')
        write_ledger(native_steps=49900000)
        rejects('50M_native_reservation',lambda:campaign.reserve('training','test',out/'none',1),'NATIVE_RESERVATION_HARD_CAP')
        write_ledger(attempts=[dict(id='owned',settled=False,reserved_native_steps=165000)])
        rejects('single_environment',lambda:campaign.reserve('training','test',out/'none',1),'CONCURRENT_PHYSICS_DENIED')
        write_ledger();(out/'STOP_REQUESTED').write_text('synthetic guard test\n')
        rejects('explicit_stop',campaign.check_resources,'EXPLICIT_STOP_REQUESTED')
        (out/'STOP_REQUESTED').unlink();campaign.HARD_STOP=time.time()-1
        rejects('hard_wall_deadline',campaign.check_resources,'HARD_STOP')
    finally:campaign.ROOT=real_root;campaign.HARD_STOP=real_deadline
    for name,kwargs,message in [
        ('RAM_reserve',dict(min_available_gib=1000),'AVAILABLE_MEMORY_RESERVE'),
        ('disk_reserve',dict(min_disk_gib=1000000),'DISK_RESERVE'),
        ('episode_wall',dict(seconds=-1),'WALL_DEADLINE'),
        ('output_size',dict(max_output_gib=1e-12),'OUTPUT_DISK_BUDGET')]:
        g=Guard(out/name,**kwargs)
        rejects(name,lambda:g.poll(admission=True),message);g.close()
    atomic(ROOT/'audit/BUDGET_RESOURCE_GUARD_TESTS.json',dict(time_utc=now(),pass_=all(x['pass_'] for x in rows),
        category='NO_PHYSICS_SHADOW_LEDGER_AND_RESOURCE_ADMISSION_TEST',tests=rows,
        actual_campaign_ledger_modified=False,physics_attempts=0,owned_training_processes_signalled=0))
    print('budget/resource guard PASS',len(rows),'negative tests; actual ledger unchanged')
if __name__=='__main__':main()
