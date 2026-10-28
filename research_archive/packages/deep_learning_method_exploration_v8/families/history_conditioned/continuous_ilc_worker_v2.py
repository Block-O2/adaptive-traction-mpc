"""V2 source candidate: true continuous ILC plus optional same-parent component BO.

No execution at import. Requires main-agent approval and the separate direct
B persistent engineering gate. No cold replay substitutes for continuation.
"""
from pathlib import Path
import copy
import fcntl
import json
import os
import random
import signal
import sys
import time
import traceback

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import persistent_worker_v1 as pw
from modal_ilc_projection_v1 import make_modal_action,project_slot_history,extract_executed_slot_statistics
from trial_interface import summarize
from continuous_bo_owner_hook_v2 import select_freeze_for_live_owner
from c2b_component_selector_v2 import ROLES as BO_ROLES, GRID as BO_GRID, digest as bo_digest
import numpy as np

base=pw.base;P=pw.P


def alarm(seconds):
    remaining=min(base.A['hard_stop_unix'],base.PLAN['physics_hard_stop_unix'])-time.time()
    if remaining<=0.:raise TimeoutError('ORIGINAL_HARD_DEADLINE')
    signal.alarm(max(1,int(min(seconds,remaining))))


class ForkAwareBridge(pw.PersistentSessionBridge):
    """Same actual session; each real child starts counting at its own fork."""
    def invoke(self,ident,interface):
        self._guard();before=self.stamp();start_s=0. if before is None else before['physical_time_s']
        model_before=self.model_counter();started=time.time();metric=None;error=None;actual_id=ident
        status='FAILED_PRESERVED'
        try:
            with self.bind():metric=self.sc.run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
            actual_id=metric['name']
            if metric.get('task_valid') is not True:raise RuntimeError('ORIGINAL_COMPLETE_TASK_NOT_VALID')
            after=self.stamp()
            if after is None or after['wall_active'] or after['planner_request_outstanding']:
                raise RuntimeError('COMPLETED_SESSION_NOT_QUIESCENT')
            if before is not None:
                for key in ['plant_identity','observer_identity','measurement_layer_identity','updater_identity']:
                    if after[key]!=before[key]:raise RuntimeError('PERSISTENT_OBJECT_REPLACED:'+key)
                if after['repetition_index']!=before['repetition_index']+1:raise RuntimeError('REPETITION_INDEX')
            status='ORIGINAL_COMPLETE_TASK';self.completed.append(actual_id)
            return metric
        except BaseException as exc:
            error=str(exc)
            if interface.child is not None:actual_id=interface.child['label']+'_'+interface.child['kind']
            raise
        finally:
            # A real fork marker is created ONLY by original mh.MatchedInterface.fork.
            # A copied common prefix is not new child computation.
            if interface.child is not None:
                start_s=float(interface.child['physical_time_at_fork'])
                model_before=interface.child.get('main_api_counter_at_fork')
            after=self.stamp();model_after=self.model_counter()
            steps=None if after is None else self._steps(start_s,after['physical_time_s'])
            self.emit('PERSISTENT_DELTA_ACCOUNTING/'+actual_id,dict(id=actual_id,kind='FORK_AWARE_PERSISTENT_TASK_INCREMENT',
                status=status,error=error,before=before,after=after,
                actual_new_native_steps=steps,actual_new_simulation_seconds=None if steps is None else steps*self.rt.NOMINAL_PHYSICS_DT_S,
                actual_new_main_model_calls=None if model_before is None or model_after is None else model_after-model_before,
                counter_origin_s=start_s,real_fork=interface.child is not None,
                task_JF_unchanged=None if metric is None else metric.get('J_F'),
                common_parent_prefix_counted_in_child=False,boundary_counted_separately=True,
                wall_s=time.time()-started,human_state_assignment=False))


def complete_causal_history(ident,it,bridge):
    with np.load(P/'runtime/source/results'/ident/'trace.npz',allow_pickle=False) as z:
        last=int(np.flatnonzero(z['stage']=='TASK')[-1])
        if not bool(z['terminal_boundary_node'][last]):raise RuntimeError('REAL_TERMINAL_BOUNDARY_REQUIRED')
        endrow=dict(time_s=float(z['time_s'][last]),phase=str(z['task_phase'][last]),
            estimated_q_dq=z['estimated_human_state_rad_rad_s'][last].tolist(),
            reference_q_dq=np.r_[z['reference_q_rad'][last],z['reference_dq_rad_s'][last]].tolist(),
            measured_force=z['physical_cuff_force_world_n'][last].tolist(),
            measured_moment=z['physical_cuff_moment_world_nm'][last].tolist(),truth_used=False)
    summary=base.read('runtime/source/results/'+ident+'/summary.json')
    commit=next(r for r in summary['task']['phase_transitions'] if r['to']=='COMPLETE')
    if not np.array_equal(np.asarray(commit['estimated_state']),np.asarray(endrow['estimated_q_dq'])):
        raise RuntimeError('TERMINAL_ESTIMATOR_COMMIT')
    endrow['source_sample_time_s']=float(commit['state_source_time_s'])
    rows=it.causal+[endrow];start=rows[0]['reference_q_dq'][:2]
    goal=np.asarray(bridge.context['spec'].outbound_goal_target_rad).tolist()
    h=summarize(rows,trial_id=ident,patient_id=base.GROUP,trial_number=bridge.context['repetition_index'],
        actual_action_tag=it.actual_tag,task_start_s=rows[0]['time_s'],task_end_s=endrow['time_s'],complete=True,
        identity=dict(case_sha256=base.C['case_sha256'],source_manifest_sha256=base.sha(P/'jobs'/base.GROUP/'SOURCE_MANIFEST.json')),
        public_phase_targets={'OUTBOUND':[start,goal],'RETURN':[goal,start]})
    metric=base.read('runtime/output/'+ident+'.json')
    if abs(h['JF_N_s']-metric['J_F'])>1e-6 or abs(h['JM_Nm_s']-metric['moment_integral'])>1e-6:
        raise RuntimeError('COMPLETE_CAUSAL_INTEGRAL_CLOSURE')
    base.put('history/'+ident+'_COMPLETE_HISTORY.json',h)
    return h,rows


def result_row(ident,it,bridge,reference_id):
    metric=pw.fix_incremental_metric(ident);measured=base.am.measure(ident)
    reference=measured if reference_id==ident else base.read('runtime/reports/'+reference_id+'_MEASURED.json')
    comparison=base.am.compare(measured,reference)
    qualified=bool(comparison['acceptance_pass'] and measured['native_physical_audit']['pass_']
        and measured['axes']['PHYSICAL_TASK_VALID']=='PASS' and measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS'
        and measured['axes']['LEGACY_R2_MATCHED']=='PASS')
    h,rows=complete_causal_history(ident,it,bridge)
    summary=base.read('runtime/source/results/'+ident+'/summary.json')
    lineage=base.read('runtime/reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
    owner={r['decision_index']:r for r in lineage['rows']};modal=[]
    for record in summary['learning_records']:
        meta=record.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')
        if meta is None:continue
        if not np.array_equal(np.asarray(meta['parameters']),np.asarray(it.active_action['x'])):
            raise RuntimeError('FROZEN_MODAL_PARAMETER_IDENTITY')
        own=owner.get(record['decision_index'],{})
        nominal_change=float(np.max(np.abs(np.asarray(meta['proposed_target_rad'])-np.asarray(meta['original_target_rad']))))
        modal.append(dict(decision_index=record['decision_index'],metadata=meta,
            activated=record.get('selected_plan_activated'),owned_native_steps=own.get('actual_native_steps',0),
            actual_reference_action_changed=bool(meta['status']=='ACCEPTED' and record.get('selected_plan_activated') is True
                and own.get('actual_native_steps',0)>0 and nominal_change>1e-12)))
    action_change=any(r['actual_reference_action_changed'] for r in modal)
    recipe_audit=dict(status='NOT_APPLICABLE_OR_NONZERO_MODAL_PARENT_TRACE',rows=[])
    if it.active_action['family']=='H150' or (it.active_action['family']=='modal8_retimed' and not any(it.active_action['x'])):
        components=[];component_pass=True
        for key,field in [('second_round_posture','posture'),('early_return_duration','early'),('terminal_hip_timing','timing')]:
            found=[]
            for record in summary['learning_records']:
                meta=record.get('selected_plan',{}).get('execution_screen',{}).get(key)
                if meta is not None:
                    own=owner.get(record['decision_index'],{})
                    found.append(dict(metadata=meta,activated=record.get('selected_plan_activated'),owned_native_steps=own.get('actual_native_steps',0)))
            okay=len(found)==len(base.C['H150'].get(field,[])) and all(
                r['metadata']['status']=='ACCEPTED' and r['activated'] is True and r['owned_native_steps']>0 for r in found)
            component_pass=component_pass and okay
            components.append(dict(component=field,expected_count=len(base.C['H150'].get(field,[])),rows=found,pass_=okay))
        recipe_audit=dict(status='PASS' if component_pass else 'FAIL',rows=components)
        qualified=qualified and component_pass
    row=dict(id=ident,action=it.active_action,complete=True,qualified=qualified,JF=measured['J_F_N_s'],JM=measured['moment_integral_Nm_s'],
        actual_new_native_steps=pw.ACCOUNTING[ident]['actual_new_native_steps'],motion_vs_B=comparison,
        axes=measured['axes'],original_physical_audit=measured['native_physical_audit'],history_sha256=h['history_sha256'],
        source_scope='REAL_CONTINUOUS_SESSION_LIVE_PARENT_FORK',stage=it.stage,tag=it.actual_tag,
        continuation_origin=it.continuation_origin,session_after=bridge.stamp(),modal_execution=modal,
        actual_modal_action_changed=action_change,original_receipt_ownership=lineage['status'],
        full_H150_component_execution=recipe_audit,
        nonzero_modal_proposal_not_execution=bool(it.active_action.get('x',[0.]*8)[3]!=0. and not action_change))
    strong=P/'runtime/reports'/(it.stage_prefix+'_H150_MEASURED.json')
    if strong.is_file() and it.actual_tag!='B':
        fixed=json.loads(strong.read_text());strong_result=P/'attempts'/(it.stage_prefix+'_H150_RESULT.json')
        strong_qualified=json.loads(strong_result.read_text()).get('qualified') if strong_result.exists() else qualified if it.actual_tag=='H150' else None
        row['paired_vs_H150']=dict(delta_JF_N_s=row['JF']-fixed['J_F_N_s'],delta_JM_Nm_s=row['JM']-fixed['moment_integral_Nm_s'],
            strong_original_qualified=strong_qualified,both_original_qualified=bool(qualified and strong_qualified),
            force_increment_claim_allowed=bool(qualified and strong_qualified and action_change))
    base.put('attempts/'+ident+'_RESULT.json',row);base.append('ALL_RESULTS.jsonl',row)
    return row,h,rows


class StageStudy(pw.DirectB):
    def __init__(self,stage_prefix,stage,bridge,arms,continuation_origin):
        super().__init__(stage_prefix+'_parent',bridge)
        self.condition=copy.deepcopy(base.C['condition']);self.condition['name']=stage_prefix
        self.stage=stage;self.stage_prefix=stage_prefix;self.arms=copy.deepcopy(arms)
        self.continuation_origin=copy.deepcopy(continuation_origin);self.actual_tag='PARENT_B'
        self.slot_requests=[];self.recorded_requests=set();self.results=[]
        self.initial_arms=copy.deepcopy(arms);self.bo_considered=False;self.bo_decision=None

    def manifest(self,b):
        m=super().manifest(b)
        m['unaugmented_scientific_interface_hash']=m['hash']
        frozen=dict(owner_version='CONTINUOUS_ILC_COMPONENT_BO_V2',arms=self.arms,continuation_origin=self.continuation_origin,stage=self.stage,stage_prefix=self.stage_prefix)
        m['continuous_contract_sha256']=base.sc.digest(frozen)
        m['hash']=base.sc.digest(dict(original=m['hash'],continuous=m['continuous_contract_sha256']))
        return m

    def control(self,b):
        request=b['request'];phase=b['task_state'].phase.value;slot=int(self.count.get(phase,0))
        if request.request_id not in self.recorded_requests:
            goal=b['spec'].outbound_goal_target_rad if phase=='OUTBOUND' else b['spec'].start_return_target_rad
            self.slot_requests.append(dict(request_id=request.request_id,phase=phase,slot=slot,
                public_phase_goal_rad=np.asarray(goal).tolist()))
            self.recorded_requests.add(request.request_id)
        base.Study.control(self,b)

    def finish(self,env,metric):
        super().finish(env,metric)
        base.put('history/'+metric['name']+'_SLOT_REQUESTS.json',self.slot_requests)

    def _consider_bo_once(self,b):
        """After original children join, before any parent control advances.

        Appending changes the policy metadata hash explicitly. The underlying
        native/scientific/interface snapshot must still equal the original B
        comparator; no original full-hash equality is claimed after append.
        """
        if self.bo_considered:return False
        self.bo_considered=True
        prefix='freeze/'+self.stage_prefix+'_'
        def emit(kind,row):base.put(prefix+kind+'.json',row)
        if self.stage!=3 or self.child is not None or self.count.get('OUTBOUND')!=0:
            raise RuntimeError('V2_BO_HOOK_NOT_ORIGINAL_T3_OWNER_OUT0')
        missing=[]
        for role in BO_ROLES:
            ident=self.stage_prefix+'_'+role;alias=P/'audit/persistent'/(ident+'_ALIAS.json')
            if alias.is_file():
                record=json.loads(alias.read_text())
                if record['new_native_steps']!=0:raise RuntimeError('V2_ALIAS_COST_CHANGED')
                ident=record['alias_of']
            path=P/'attempts'/(ident+'_RESULT.json')
            if not path.is_file() or json.loads(path.read_text()).get('complete') is not True:missing.append(role)
        if missing or getattr(self,'nonzero_not_run_reason',None):
            self.bo_decision=dict(status='ABSTAIN',reason='ORIGINAL_REGISTERED_ROLES_NOT_ALL_COMPLETE',missing_roles=missing,fit_matrix_solves=0)
            emit('C2B_V2_PRECONDITION_ABSTAIN',self.bo_decision);return False
        before=self.manifest(b)
        decision=select_freeze_for_live_owner(self,b,root=P,group=base.GROUP,config=base.C,
            original_quiesce=base.mh.fc.quiesce,original_compare_raw=base.frozen.bc.compare_raw,
            emit_frozen=emit,stop_check=pw.stop_check)
        after_fit=self.manifest(b);self.bo_decision=decision
        if after_fit['hash']!=before['hash']:raise RuntimeError('V2_FIT_CHANGED_ORIGINAL_FULL_SNAPSHOT')
        if decision.get('status')!='PROPOSE_ONE_FROZEN_GRID_ACTION':return False
        if base.C.get('c2b_component_bo_v2_candidate_physics_authorized') is not True:
            emit('C2B_V2_PROPOSAL_NOT_RUN',dict(reason='SEPARATE_CANDIDATE_PHYSICAL_APPROVAL_MISSING',decision=decision));return False
        action=copy.deepcopy(decision['selected_action']);x3=float(action['x'][3])
        if x3 not in BO_GRID or any(abs(x3-float(r['action'].get('x',[0.]*8)[3]))<=1e-12 for r in self.results if r['action']['family']!='B'):
            raise RuntimeError('V2_PROPOSAL_NOT_NEW_REGISTERED_GRID_ACTION')
        if time.time()>=min(base.PLAN['dispatch_cutoff_unix'],base.PLAN['physics_hard_stop_unix'])-base.PLAN['physical_timeout_s']:
            emit('C2B_V2_PROPOSAL_NOT_RUN',dict(reason='ORIGINAL_DISPATCH_OR_PHYSICAL_RESERVE',decision=decision));return False
        comparator=base.read('runtime/reports/'+self.stage_prefix+'_B_SNAPSHOT.json')
        for key in ['native_hash','unaugmented_scientific_interface_hash']:
            if before[key]!=comparator[key]:raise RuntimeError('V2_PARENT_CHANGED_FROM_EXISTING_COMPARATORS:'+key)
        candidate=dict(tag='BO_V2_NEW',action=action,selection_sha256=bo_digest(decision),
            preappend_parent_full_hash=before['hash'],same_native_parent_as_original_comparators=True)
        frozen=dict(candidate=candidate,decision=decision,source_observation_bundle_sha256=decision['input_sha256'],
            frozen_unix=time.time(),before_new_candidate_START=True)
        emit('C2B_V2_FROZEN_NEW_ARM',frozen)
        self.arms.append(candidate)
        augmented=self.manifest(b)
        for key in ['native_hash','unaugmented_scientific_interface_hash']:
            if augmented[key]!=before[key]:raise RuntimeError('V2_METADATA_APPEND_CHANGED_SCIENTIFIC_PARENT:'+key)
        emit('C2B_V2_ARMS_METADATA_CHANGE',dict(original_arms=self.initial_arms,final_arms=self.arms,
            before_full_hash=before['hash'],after_full_hash=augmented['hash'],full_hash_changed=before['hash']!=augmented['hash'],
            before_policy_metadata_hash=before['continuous_contract_sha256'],after_policy_metadata_hash=augmented['continuous_contract_sha256'],
            native_hash_unchanged=True,scientific_interface_hash_unchanged=True,original_comparator_full_hash=comparator['hash'],
            claim='Only registered arms software metadata changed; never claim original full hash unchanged after append',
            new_arm_count=1,physical_dispatch='next iteration of original actual fork loop'))
        return True

    def decision_boundary(self,b):
        if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']==0:
            self.fork_done=True
            arm_index=0
            while True:
                if arm_index>=len(self.arms):
                    if self.stage==3 and not self.bo_considered and self._consider_bo_once(b):continue
                    break
                arm=self.arms[arm_index];arm_index+=1
                tag=arm['tag'];action=arm['action'];ident=self.stage_prefix+'_'+tag
                # These are the same parent and frozen action. Reuse identical
                # prior arm raw explicitly; do not pay/count duplicate physics.
                previous=next((r for r in self.results if base.sc.digest(r['action'])==base.sc.digest(action)),None)
                if previous is not None:
                    alias=dict(tag=tag,action=action,alias_of=previous['id'],new_native_steps=0,
                        status='REUSED_IDENTICAL_FROZEN_ACTION_NOT_NEW_SAMPLE')
                    base.put('audit/persistent/'+ident+'_ALIAS.json',alias);continue
                if self.stage==3 and tag not in ['B','H150','ZERO_MODAL']:
                    zero_gate=self.stage_prefix+'_ZERO_MODAL_RAW_GATE'
                    if not base.read('audit/persistent/'+zero_gate+'.json')['status']=='PASS':
                        raise RuntimeError('T3_ZERO_MODAL_EQUIVALENCE_NOT_PASSED')
                failed=None;alarm(base.C.get('nested_owner_timeout_s',3600))
                try:
                    if self.fork(b,tag,np.zeros((2,5,3))):
                        self.ident=ident;self.actual_tag=tag
                        self.current=copy.deepcopy(base.C['B'] if action['family']=='B' else base.C['H150'])
                        self.current['id']=ident;self.active_action=copy.deepcopy(action);self.rule_action=copy.deepcopy(action)
                        self.active_policy_tag=tag;self.causal=[];self.references={};self.sample_rows=[];self.terminal_intent=None
                        self.slot_requests=[];self.recorded_requests=set();self.actual_plant_binding_saved=False
                        self.invocation_start_s=float(self.child['physical_time_at_fork']);self.last_counter=0.
                        base.put('owned/'+ident+'_PROCESS.json',dict(pid=os.getpid(),parent_pid=os.getppid(),process_group=os.getpgrp(),
                            start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
                            actual_real_fork=True,outer_stage=self.stage,stage_owner=self.stage_prefix,
                            inherited_native_session=self.bridge.stamp(),unique_child_identity=copy.deepcopy(self.child)))
                        alarm(base.PLAN['physical_timeout_s'])
                        return self.control(b)
                except AssertionError as exc:
                    if not str(exc).startswith(('CHILD_FAILED:','NATIVE_PHYSICAL_FAILURE:')):raise
                    failed=str(exc)
                    if self.active_owned_child_pid is not None or not self.parent_checks[-1]['unchanged']:
                        raise RuntimeError('FAILED_CHILD_DID_NOT_PRESERVE_PARENT')
                row_path=P/'attempts'/f'{ident}_RESULT.json'
                if row_path.exists():row=json.loads(row_path.read_text())
                else:
                    partial=P/'runtime/output'/f'{ident}_PARTIAL_COMPUTE.json'
                    row=dict(id=ident,action=action,complete=False,qualified=False,error=failed,
                        actual_new_native_steps=json.loads(partial.read_text()).get('actual_new_native_physics_steps') if partial.exists() else None)
                    base.put('attempts/'+ident+'_RESULT.json',row);base.append('ALL_RESULTS.jsonl',row)
                self.results.append(row)
                if tag=='B' and not row['qualified']:raise RuntimeError('SAME_LIVE_PARENT_B_NOT_QUALIFIED')
                if failed and row.get('original_physical_audit',{}).get('pass_') is False:
                    raise RuntimeError('ORIGINAL_NATIVE_SAFETY_FAILURE_PRESERVED')
                if self.stage==3 and tag=='ZERO_MODAL':
                    gate=base.frozen.bc.compare_raw(P/'runtime/source/results'/ident,
                        P/'runtime/source/results'/(self.stage_prefix+'_H150'))
                    base.put('audit/persistent/'+self.stage_prefix+'_ZERO_MODAL_RAW_GATE.json',gate)
                    if gate['status']!='PASS':raise RuntimeError('T3_ZERO_MODAL_NOT_EQUIVALENT')
                    strong_row=base.read('attempts/'+self.stage_prefix+'_H150_RESULT.json')
                    if not row['qualified'] or not strong_row['qualified']:
                        self.nonzero_not_run_reason='T3_H150_OR_ZERO_ORIGINAL_RECIPE_NOT_QUALIFIED'
                        base.put('jobs/'+self.stage_prefix+'/NONZERO_NOT_RUN.json',dict(reason=self.nonzero_not_run_reason,
                            H150=strong_row,ZERO_MODAL=row,failed_strong_result_preserved=True))
                        break
                base.put('jobs/'+self.stage_prefix+'/PROGRESS.json',dict(rows=self.results,parent_checks=self.parent_checks))
            if self.stage==3 and not self.bo_considered:self._consider_bo_once(b)
            alarm(base.PLAN['physical_timeout_s'])
        self.control(b)


def boundary(bridge,ident):
    base.dispatch(ident,kind='ORIGINAL_CONTINUOUS_INTER_REP_BOUNDARY',session_before=bridge.stamp())
    alarm(base.PLAN['physical_timeout_s'])
    try:
        answer=bridge.advance_boundary(ident,max_wait_s=2.)
        if not pw.ACCOUNTING[ident]['counter_matches_observation']:raise RuntimeError('BOUNDARY_NATIVE_COUNT')
        base.put('audit/persistent/'+ident+'_CAUSAL_COST.json',answer)
        base.mh.event('END',ident,returncode=0,joined=True,actual_new_native_steps=pw.ACCOUNTING[ident]['actual_new_native_steps'])
        return answer
    except BaseException as exc:
        base.mh.event('END',ident,returncode=1,joined=True,error=str(exc),
            actual_new_native_steps=pw.ACCOUNTING.get(ident,{}).get('actual_new_native_steps'));raise
    finally:signal.alarm(0)


def continue_own_h150(ident,it,bridge,row,history,causal_rows):
    if not row['qualified']:
        base.put('jobs/'+ident+'/CONTINUATION_END.json',dict(status='NOT_RUN_T2_H150_NOT_QUALIFIED',T2_result=row));return
    zero_id=it.stage_prefix+'_ZERO_MODAL'
    if not base.read('attempts/'+zero_id+'_RESULT.json')['qualified']:
        raise RuntimeError('T2_ZERO_MODAL_ORIGINAL_RECIPE_NOT_QUALIFIED')
    gate=base.frozen.bc.compare_raw(P/'runtime/source/results'/ident,P/'runtime/source/results'/zero_id)
    base.put('audit/persistent/'+ident+'_T2_ZERO_MODAL_RAW_GATE.json',gate)
    if gate['status']!='PASS':raise RuntimeError('T2_ZERO_MODAL_NOT_EQUIVALENT_NO_ILC')
    summary=base.read('runtime/source/results/'+ident+'/summary.json')
    lineage=base.read('runtime/reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
    statistics=extract_executed_slot_statistics(causal_rows,it.slot_requests,summary,lineage)
    enabled=project_slot_history(statistics,gain=.25);small=project_slot_history(statistics,gain=.10)
    arms=[dict(tag='B',action={'family':'B'}),dict(tag='H150',action={'family':'H150','legacy':[0.,0.]}),
          dict(tag='ZERO_MODAL',action=make_modal_action(0.)),
          dict(tag='ILC_ENABLED_G025',action=make_modal_action(enabled['x3'])),
          dict(tag='ILC_ENABLED_G010',action=make_modal_action(small['x3'])),
          dict(tag='FIXED_X3_MINUS025',action=make_modal_action(-.25)),
          dict(tag='FIXED_X3_PLUS025',action=make_modal_action(.25))]
    disabled=dict(status='NOT_RUN_NO_FROZEN_POPULATION;zero_update_only_weak_ablation')
    if base.C.get('ilc_population_history'):
        population_path=P/base.C['ilc_population_history']
        if base.sha(population_path)!=base.C.get('ilc_population_history_sha256'):raise RuntimeError('POPULATION_IDENTITY_CHANGED')
        population=json.loads(population_path.read_text())
        if population.get('frozen_before_current_T1') is not True:raise RuntimeError('POPULATION_NOT_PRIOR_FROZEN')
        disabled=project_slot_history(population['slot_statistics'],gain=.25)
        arms.append(dict(tag='ILC_HISTORY_DISABLED',action=make_modal_action(disabled['x3'])))
    frozen=dict(arms=arms,enabled=enabled,smaller_gain=small,disabled=disabled,actual_source_trial=ident,
        history_sha256=history['history_sha256'],slot_statistics=statistics,frozen_unix=time.time(),
        source_completed_before_next_boundary=True,future_T3_results_consumed=False,
        source_native_session=bridge.stamp(),x3_objective='prior_reference_error_projection_not_force_gradient')
    base.put('freeze/'+ident+'_T3_DECISIONS.json',frozen)
    # Still inside the true H150 child, after its own T2 sc.run finalized and
    # updated this process's session_context. No external B state is used.
    boundary(bridge,ident+'_BOUNDARY_2_3')
    stage_prefix=ident+'_T3'
    run_stage(bridge,stage_prefix,3,arms,dict(previous_actual_trial=ident,
        previous_history_sha256=history['history_sha256'],same_native_objects=True,
        frozen_decision_sha256=base.sha(P/'freeze'/(ident+'_T3_DECISIONS.json'))))
    base.put('jobs/'+ident+'/CONTINUATION_END.json',dict(status='T3_EXECUTED_WITH_REPORTED_QUALIFICATIONS',
        real_previous_trial=ident,session_after=bridge.stamp(),all_nested_children_joined=True))


def run_stage(bridge,stage_prefix,stage,arms,origin):
    it=StageStudy(stage_prefix,stage,bridge,arms,origin);ident=stage_prefix+'_parent'
    base.dispatch(ident,kind='REAL_PERSISTENT_LIVE_PARENT',stage=stage,continuation_origin=origin,session_before=bridge.stamp())
    alarm(base.C.get('nested_owner_timeout_s',3600));started=time.time()
    try:
        metric=bridge.invoke(ident,it);signal.alarm(0)
        if it.child is not None:
            actual=it.child['label']+'_'+it.child['kind']
            row,history,causal_rows=result_row(actual,it,bridge,it.stage_prefix+'_B' if it.actual_tag!='B' else actual)
            # Original fork owner, not this child, writes its joined END after
            # this entire chain exits. Native increment remains this task only.
            if stage==2 and it.actual_tag=='H150':
                try:continue_own_h150(actual,it,bridge,row,history,causal_rows)
                except BaseException as exc:
                    base.put('jobs/'+actual+'/CONTINUATION_END.json',dict(status='FAILED_PRESERVED',
                        error=str(exc),traceback=traceback.format_exc(),T2_task_result_preserved=True));raise
            base.put('owned/'+actual+'_EXIT.json',dict(pid=os.getpid(),utc=base.utc(),returncode=0,
                actual_real_fork=True,active_nested_child=getattr(it,'active_owned_child_pid',None),
                bridge_running=bridge.running,own_task_native_steps=pw.ACCOUNTING[actual]['actual_new_native_steps']))
            os._exit(0)
        pw.fix_incremental_metric(ident);parent_m=base.am.measure(ident)
        same=base.frozen.bc.compare_raw(P/'runtime/source/results'/ident,P/'runtime/source/results'/(stage_prefix+'_B'))
        base.put('audit/persistent/'+stage_prefix+'_PARENT_B_RAW_GATE.json',same)
        if same['status']!='PASS':raise RuntimeError('LIVE_PARENT_B_RAW_CHANGED')
        row=dict(id=ident,complete=True,qualified=True,action={'family':'B'},JF=parent_m['J_F_N_s'],JM=parent_m['moment_integral_Nm_s'],
            actual_new_native_steps=pw.ACCOUNTING[ident]['actual_new_native_steps'],scope='ACTUAL_PARENT_COMPUTE_NOT_ANOTHER_INDEPENDENT_SAMPLE',stage=stage)
        base.put('attempts/'+ident+'_RESULT.json',row);base.append('ALL_RESULTS.jsonl',row)
        base.mh.event('END',ident,returncode=0,joined=True,actual_new_native_steps=row['actual_new_native_steps'],
            stage=stage,wall_seconds=time.time()-started,descendant_native_counted_separately=True)
        base.put('jobs/'+stage_prefix+'/STAGE_DONE.json',dict(status='COMPLETED_REPORTED_QUALIFICATIONS',rows=it.results,
            parent_gate=same,parent_checks=it.parent_checks,session_after=bridge.stamp(),
            nonzero_not_run_reason=getattr(it,'nonzero_not_run_reason',None),
            bo_considered=it.bo_considered,bo_decision=it.bo_decision,original_arms=it.initial_arms,final_arms=it.arms))
        return it.results
    except BaseException as exc:
        actual=ident if it.child is None else it.child['label']+'_'+it.child['kind']
        base.put('audit/persistent/'+actual+'_ERROR.json',dict(error=str(exc),traceback=traceback.format_exc(),
            session=bridge.stamp(),actual_task_increment=pw.ACCOUNTING.get(actual)))
        if it.child is not None:
            base.put('owned/'+actual+'_EXIT.json',dict(pid=os.getpid(),utc=base.utc(),returncode=1,
                actual_real_fork=True,active_nested_child=getattr(it,'active_owned_child_pid',None),
                bridge_running=bridge.running,error=str(exc)))
            os._exit(1)
        if not any(r['event']=='END' and r['id']==ident for r in base.mh.records()):
            base.mh.event('END',ident,returncode=1,joined=True,error=str(exc),
                actual_new_native_steps=pw.ACCOUNTING.get(ident,{}).get('actual_new_native_steps'))
        raise
    finally:signal.alarm(0)


def main():
    if base.C.get('continuous_ilc_contract')!='CONTINUOUS_ILC_RETURN_X3_V1' or base.C.get('continuous_ilc_physics_authorized') is not True:
        raise RuntimeError('MAIN_AGENT_CONTINUOUS_ILC_APPROVAL_REQUIRED')
    if base.C.get('continuous_owner_version')!='CONTINUOUS_ILC_COMPONENT_BO_V2':
        raise RuntimeError('EXPLICIT_NEW_V2_OWNER_CONFIG_REQUIRED')
    engineering=P/base.C['persistent_B_gate_path']
    if base.sha(engineering)!=base.C['persistent_B_gate_sha256'] or json.loads(engineering.read_text())['status']!='PERSISTENT_B_ENGINEERING_GATE_PASS':
        raise RuntimeError('PREREQUISITE_PERSISTENT_B_GATE_NOT_PASSED')
    if base.C.get('known_heavy_engineering') is not True:raise RuntimeError('KNOWN_HEAVY_ENGINEERING_SCOPE_ONLY')
    lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    import v8_case_adapter_v1 as adapter
    installed=adapter.install(base.sc,base.C,P,base.sha,base.put)
    base.put('audit/persistent/'+base.GROUP+'_CASE_SCOPE.json',dict(first_task_cold=True,later_tasks_cold=False,
        adapter_install_preserved=installed,actual_continuation='each real process-local session_context',
        learned_model_used=False,source_only_contract_reviewed=True))
    pw.freeze_sources()
    base.SOURCE_MANIFEST['engineering_contract']='CONTINUOUS_ILC_COMPONENT_BO_V2'
    for name in ['continuous_ilc_worker_v1.py','continuous_ilc_worker_v2.py','modal_ilc_projection_v1.py',
                 'c2b_component_selector_v2.py','c2b_evidence_bundle_v2.py','continuous_bo_owner_hook_v2.py','C2B_COMPONENT_BO_CONTRACT_V2.json']:
        file=HERE/name;base.SOURCE_MANIFEST['files'][str(file.relative_to(P))]=base.sha(file)
    if base.C.get('ilc_population_history'):
        path=P/base.C['ilc_population_history'];expected=base.C['ilc_population_history_sha256']
        if base.sha(path)!=expected:raise RuntimeError('PRIOR_POPULATION_CHANGED')
        base.SOURCE_MANIFEST['files'][base.C['ilc_population_history']]=expected
    base.put('jobs/'+base.GROUP+'/SOURCE_MANIFEST.json',base.SOURCE_MANIFEST)
    random.seed(base.C['condition']['seed']);np.random.seed(base.C['condition']['seed'])
    def stop_signal(signum,_frame):raise KeyboardInterrupt('OWNED_PROCESS_TREE_SIGNAL:'+str(signum))
    signal.signal(signal.SIGINT,stop_signal);signal.signal(signal.SIGTERM,stop_signal)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('REGISTERED_LOCAL_OR_TREE_TIMEOUT')))
    bridge=ForkAwareBridge(base.sc.rt,base.sc,emit=pw.emit,
        hard_deadline_unix=min(base.A['hard_stop_unix'],base.PLAN['physics_hard_stop_unix']),stop_check=pw.stop_check,model_counter=pw.model_counter)
    try:
        first,_=pw.run_task(base.GROUP+'_T1_B',bridge,1)
        boundary(bridge,base.GROUP+'_BOUNDARY_1_2')
        arms=[dict(tag='B',action={'family':'B'}),dict(tag='ZERO_MODAL',action=make_modal_action(0.)),
              dict(tag='H150',action={'family':'H150','legacy':[0.,0.]})]
        rows=run_stage(bridge,base.GROUP+'_T2',2,arms,dict(previous_actual_trial=first['id'],same_native_objects=True))
        base.put('jobs/'+base.GROUP+'/WORKER_DONE.json',dict(status='CONTINUOUS_ILC_COMPONENT_BO_V2_COMPLETED_REPORTED_RESULTS',
            T1=first,T2_rows=rows,all_children_joined=True,all_native_increments_separately_registered=True,
            independent_generalization=False,nonlinear_force_sensitivity_identified=False))
    except BaseException as exc:
        base.put('jobs/'+base.GROUP+'/WORKER_DONE.json',dict(status='FAILED_PRESERVED',error=str(exc),traceback=traceback.format_exc(),
            accounting=pw.ACCOUNTING,session=bridge.stamp()));raise
    finally:
        signal.alarm(0);base.put('owned/'+base.GROUP+'_EXIT.json',dict(pid=os.getpid(),utc=base.utc(),
            active_child=None,bridge_running=bridge.running,all_computation_foreground=True))


if __name__=='__main__':main()
