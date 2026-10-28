"""Explicit recovery of a saved complete rollout; no new physical attempt.

Restore pre-Adam policy/Adam/RNG, replay the complete retained update and commit
a new generation. Partially updated emergency weights are never promoted.
"""
from pathlib import Path
import os,sys,json,time,fcntl
from research_common import ROOT,RUNTIME,atomic,read,ledger,decision,sha,now,check_resources,NO_TRAIN,same_pid
os.environ['IHEAR_RUN_DIR']=str(ROOT/'runtime/recovery_interface')
import worker
from worker import np,snapshot,load,save,PilotEnv,update,configure

def main():
    assert '--recover-approved' in sys.argv,'EXPLICIT_NEXT_STAGE_UPDATE_RECOVERY_AUTHORIZATION_REQUIRED'
    assert read(ROOT/'ACTIVATION.json',{}).get('training_authorized_for_next_stage'),'NEXT_STAGE_NOT_AUTHORIZED'
    check_resources();assert time.time()<NO_TRAIN,'NO_NEW_TRAINING_WINDOW'
    for name,h in read(ROOT/'ACTIVATION.json')['script_sha256'].items():assert sha(ROOT/'scripts'/name)==h,'SOURCE_CHANGED:'+name
    value=read(ROOT/'LEDGER.json',dict(attempts=[]))
    assert not any(not x['settled'] for x in value['attempts']),'UNSETTLED_PHYSICAL_ATTEMPT'
    for p in (ROOT/'owned').glob('*.json'):
        r=read(p);assert not same_pid(r.get('worker')),'OWNED_WORK_STILL_ACTIVE'
    run=Path(sys.argv[1]);out=Path(sys.argv[2]);assert out.resolve().is_relative_to(RUNTIME/'recovery')
    out.mkdir(parents=True,exist_ok=False)
    base=run/'before_update_checkpoint';input_path=run/'COMPLETE_UPDATE_INPUT.json'
    before=read(base.with_suffix('.json'));assert before['phase']=='COMPLETE_ROLLOUT_BEFORE_ADAM'
    assert sha(input_path)==before['input_sha256']
    assert not any(x.get('original_input_sha256')==before['input_sha256'] for x in value.get('offline_update_recoveries',[])),'ROLLOUT_RECOVERY_ALREADY_RECORDED'
    interface=PilotEnv(out/'interface/env');model,meta=load(base,interface);interface.close()
    assert snapshot(model)==meta['state_snapshot']
    cfg=meta['research_config'];model.set_logger(configure(str(out/'logger'),['csv']))
    samples=read(input_path)
    for s in samples:
        for key in ['obs','next_obs','raw_action','action','mean','std']:
            if key in s:s[key]=np.asarray(s[key],np.float32)
    result=update(model,samples,cfg['rollout'],out)
    cp=out/'recovered_checkpoint';save(model,cp,dict(seed=cfg['seed'],branch=cfg['branch'],
        continuation_episodes=meta['continuation_episodes'],research_config=cfg,parent=str(base),
        state_snapshot=snapshot(model),recovery='COMPLETE_ROLLOUT_REPLAY_NO_NEW_PHYSICS',
        original_input_sha256=sha(input_path),additional_Adam_updates=result['optimizer_steps']))
    with ledger() as value:
        value['optimizer_steps']+=result['optimizer_steps'];value['gradient_train_calls']+=1
        value.setdefault('offline_update_recoveries',[]).append(dict(run=str(run),out=str(out),
              checkpoint=str(cp),additional_Adam_updates=result['optimizer_steps'],native_steps=0,
              new_training_attempts=0,original_input_sha256=before['input_sha256'],time_utc=now()))
    atomic(out/'RESULT.json',dict(checkpoint=str(cp),update=result,physical_attempts=0,native_steps=0))
    decision('OFFLINE_UPDATE_RECOVERED',dict(run=str(run),checkpoint=str(cp),additional_Adam_updates=result['optimizer_steps']),
             'Resume explicitly versioned physical continuation from recovered complete-update checkpoint')
    print(json.dumps(dict(checkpoint=str(cp),additional_Adam_updates=result['optimizer_steps'])))
if __name__=='__main__':
    with (ROOT/'.campaign.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main()
