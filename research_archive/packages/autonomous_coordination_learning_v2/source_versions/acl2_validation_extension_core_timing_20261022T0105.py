"""One finite validation extension, allocated by time alone, not outcomes."""
import copy,time,json
from acl2_shared import P,R,read,put,sha,utc,decision

def main():
    assert not (P/'VALIDATION_TIME_EXTENSION_LOCK.json').exists(),'EXTENSION_ALREADY_ALLOCATED'
    A=read('ACTIVATION.json');plan=read('runtime/RUN_PLAN.json');original=read('VALIDATION_INPUT_LOCK.json');frozen=read('FROZEN_SELECTION.json');allocation=read('VALIDATION_ALLOCATION.json');registered=read('LOCKED_VALIDATION_PLAN.json')['conditions'];history=read('history/RECOVERY_TEST_PLAN.json')
    # Deliberately do not read JF/JM/qualification or fit any model here.
    n_original=allocation['independent_states'];remaining=registered[n_original:];per=allocation['planning_seconds_per_attempt'];per_state=4+len(frozen['unique_candidates']);parent_extra=90.
    last_dispatch=plan['physics_hard_stop_unix']-plan['physical_timeout_s']
    expected_state_seconds=per_state*per+parent_extra
    available=max(0.,last_dispatch-time.time());n_extra=max(0,min(len(remaining),int(available//expected_state_seconds)))
    newjobs=[];configs={}
    # Same frozen actions and frozen GP; source module included in initial lock.
    from acl2_freeze_validate import pred
    for offset,state in enumerate(remaining[:n_extra]):
        index=n_original+offset+1;group='LOCKED_STATE_%d'%index;condition=copy.deepcopy(state);condition['name']=group;acts=[dict(tag='B',action=dict(family='B')),dict(tag='H150',action=dict(family='legacy2',legacy=[0,0])),dict(tag='STRONG',action=frozen['base']['action'])]
        for tag,action in frozen['unique_candidates'].items():acts.append(dict(tag='FROZEN_'+tag,action=action,prediction=pred(action.get('x',[0]*8),frozen['model'],frozen['nominal_table'],frozen['base'])))
        for a in acts:a['category']='validation'
        config=dict(group=group,condition=condition,B=history['arms'][0],H150=history['arms'][1],actions=acts,mode='validation',local_stop_unix=plan['physics_hard_stop_unix'])
        path='jobs/'+group+'_CONFIG.json';assert not (P/path).exists(),'NO_EXISTING_CONFIG_OVERWRITE';put(path,config);put('runtime/'+group+'_TEST_PLAN.json',dict(condition=condition,arms=history['arms']));configs[path]=sha(P/path)
        jid='%03d_%s'%(100+offset,group);newjobs.append(dict(id=jid,script='acl2_validation_worker.py',args=[path],timeout_s=int(expected_state_seconds*1.2+120),latest_start_unix=last_dispatch-expected_state_seconds*(n_extra-offset-1),requires=['VALIDATION_TIME_EXTENSION_LOCK.json']))
    lock=dict(utc=utc(),new_states=n_extra,original_states=n_original,selected_registered_prefixes=remaining[:n_extra],remaining_not_run=remaining[n_extra:],planning_seconds_per_attempt=per,expected_seconds_per_state=expected_state_seconds,available_seconds_before_last_dispatch=available,last_dispatch_unix=last_dispatch,source_sha256=sha(__file__),original_validation_lock_sha256=sha(P/'VALIDATION_INPUT_LOCK.json'),frozen_selection_sha256=sha(P/'FROZEN_SELECTION.json'),configs=configs,validation_job_ids=[j['id'] for j in newjobs],allocation_uses_outcomes=False,no_new_training_or_tuning=True)
    assert lock['frozen_selection_sha256']==original['selection_sha256'],'FROZEN_CANDIDATES_CHANGED'
    put('VALIDATION_TIME_EXTENSION_LOCK.json',lock)
    for job in newjobs:put('queue/'+job['id']+'.json',job)
    alljobs=original['validation_job_ids']+[j['id'] for j in newjobs]
    put('VALIDATION_QUEUE_SEALED.json',dict(utc=utc(),validation_job_ids=alljobs,extension_job_id='090_VALIDATION_TIME_EXTENSION',maximum_registered_states=len(registered),actual_allocated_states=n_original+n_extra,no_further_native_extension=True))
    decision('Conservative initial allocation can leave enough time for another registered unseen prefix','One time-only extension after initial validation queue closes',{'new_registered_states':n_extra,'available_s':available,'expected_state_s':expected_state_seconds},'No outcomes read; identical frozen candidates/models and next T0-registered prefixes; per-attempt and absolute deadlines unchanged','Execute added fixed tests, or seal queue with no extension if a whole state cannot fit',['VALIDATION_TIME_EXTENSION_PREREGISTRATION.json','VALIDATION_TIME_EXTENSION_LOCK.json','VALIDATION_QUEUE_SEALED.json'])
    print('VALIDATION_TIME_EXTENSION',n_extra,'new states; queue sealed',flush=True)

if __name__=='__main__':main()
