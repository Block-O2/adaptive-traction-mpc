"""Approved single-CPU <=120s ridge/ablation fit on the exposed six contexts."""
from pathlib import Path
import hashlib
import json
import os
import resource
import signal
import time

os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from c3b_inference import design,select

HERE=Path(__file__).resolve().parent
SHARED=HERE.parent/'critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json'
EXPECTED='ea35953cf6e8775a7331a80febf1219b2d2d047677fb2cc57db6e8baf0773ed5'
KINDS=['ACTION_ONLY','HISTORY_ADDITIVE','HISTORY_INTERACTION','COMMISSIONED25_INTERACTION']
ACTIONS=['B','LATE_H150','EARLY_H150']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,value):
    if path.exists():raise FileExistsError('NO_OVERWRITE:'+str(path))
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def best_constant(indices,outcomes):
    # Qualification count is primary; cost gain compares only qualified cases.
    scores=[]
    for a in range(3):
        valid=[g for g in indices if outcomes[g][a]['original_qualified']]
        gain=sum(outcomes[g][0]['JF_N_s']-outcomes[g][a]['JF_N_s'] for g in valid)
        scores.append((-len(valid),-gain,a))
    return min(scores)[2]


def stump_fit(indices,features,outcomes):
    best=None
    for j in range(features.shape[1]):
        unique=sorted(set(float(features[g,j]) for g in indices))
        for lo,hi in zip(unique[:-1],unique[1:]):
            threshold=(lo+hi)/2
            left=[g for g in indices if features[g,j]<=threshold]
            right=[g for g in indices if features[g,j]>threshold]
            la=best_constant(left,outcomes);ra=best_constant(right,outcomes)
            picks={g:la if g in left else ra for g in indices}
            qualified=sum(outcomes[g][a]['original_qualified'] for g,a in picks.items())
            gain=sum(outcomes[g][0]['JF_N_s']-outcomes[g][a]['JF_N_s']
                     for g,a in picks.items() if outcomes[g][a]['original_qualified'])
            key=(-qualified,-gain,j,threshold,la,ra)
            if best is None or key<best[0]:best=(key,dict(feature_index=j,threshold=threshold,left_action=la,right_action=ra))
    return best[1] if best else dict(constant_action=best_constant(indices,outcomes))


def main():
    started=time.time();cpu=time.process_time()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('REGISTERED_C3B_120S')))
    signal.alarm(120)
    out=HERE/'c3b_offline_v1';out.mkdir(exist_ok=False)
    write(out/'START.json',dict(started_unix=started,pid=os.getpid(),timeout_s=120,
        cpu_threads=1,approved_by='main_agent_explicit_message',new_physics=0))
    try:
        if sha(SHARED)!=EXPECTED:raise ValueError('SHARED_DATASET_IDENTITY_CHANGED')
        data=read(SHARED);hist=read(HERE/'V7_COMPLETE_B_HISTORY8_DATASET.json')
        groups=hist['groups'];H=np.array([r['features'] for r in hist['rows']]);history=[r['history'] for r in hist['rows']]
        names=hist['rows'][0]['feature_names'];rows=data['rows']
        prototypes=[next(r for r in rows if r['id']=='EARLYN01_'+a) for a in ACTIONS]
        recipe_hashes=[r['action_recipe_sha256'] for r in prototypes]
        matched=[];outcomes=[];commissioned=[];commissioned_names=None
        for group in groups:
            selected=[]
            for recipe_hash in recipe_hashes:
                found=[r for r in rows if r['group']==group and r['action_recipe_sha256']==recipe_hash]
                if len(found)!=1:raise ValueError('RECIPE_NOT_UNIQUE_OR_MISSING:'+group)
                r=found[0];label=r['labels_evaluation_only']
                if label['complete'] is not True or any(label.get(k) is None for k in ['JF_N_s','JM_Nm_s','original_qualified']):
                    raise ValueError('INCOMPLETE_LABEL_NOT_FILLED:'+r['id'])
                selected.append(r)
            if not selected[0]['labels_evaluation_only']['original_qualified']:
                raise ValueError('B_NOT_QUALIFIED')
            if commissioned_names is None:commissioned_names=selected[0]['context']['feature_names']
            if selected[0]['context']['feature_names']!=commissioned_names:raise ValueError('CONTEXT_ORDER')
            for r in selected[1:]:
                if r['context']['subset_numeric_identity_sha256']!=selected[0]['context']['subset_numeric_identity_sha256']:
                    raise ValueError('DIFFERENT_CONTEXT_WITHIN_PARENT')
            commissioned.append(selected[0]['context']['features'])
            matched.append(selected);outcomes.append([r['labels_evaluation_only'] for r in selected])
        C=np.array(commissioned,float)
        have_margin=all(l.get('motion_worst_ratio') is not None for labels in outcomes for l in labels)
        targets=[]
        for labels in outcomes:
            targets.append([[l['JF_N_s']-labels[0]['JF_N_s'],l['JM_Nm_s']-labels[0]['JM_Nm_s'],
                             float(l['original_qualified'])]+([l['motion_worst_ratio']-1.] if have_margin else [])
                            for l in labels])
        Y=np.array(targets,float)
        source_files=[SHARED,HERE/'V7_COMPLETE_B_HISTORY8_DATASET.json',
            HERE/'C3B_OFFLINE_TRAINING_CONTRACT_V1.json',Path(__file__),HERE/'c3b_inference.py',HERE/'trial_interface.py']
        manifest=dict(files=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in source_files],
                      recipes=[dict(tag=a,recipe_sha256=h,prototype_id=p['id'],action=p['action'],action_recipe=p['action_recipe'])
                               for a,h,p in zip(ACTIONS,recipe_hashes,prototypes)])
        write(out/'DATASET_SOURCE_MANIFEST.json',manifest)
        solves=0;fold_results=[];snapshots=[]
        def snapshot_for(train):
            nonlocal solves
            models={}
            for kind in KINDS:
                F=C if kind=='COMMISSIONED25_INTERACTION' else H
                if kind=='ACTION_ONLY':F=np.zeros((6,0))
                mu=F[train].mean(axis=0);scale=F[train].std(axis=0);scale=np.where(scale<1e-9,1.,scale)
                Z=(F-mu)/scale
                X=np.array([design(Z[g],a,kind) for g in train for a in range(3)])
                target=Y[train].reshape(-1,Y.shape[-1])
                penalty=np.eye(X.shape[1]);penalty[:3,:3]=0.
                W=np.linalg.solve(X.T@X+penalty,X.T@target);solves+=1
                models[kind]=dict(mean=mu.tolist(),scale=scale.tolist(),weights=W.tolist(),
                    design_columns=X.shape[1],training_matrix_rank=int(np.linalg.matrix_rank(X)),
                    training_contexts=[groups[g] for g in train],ridge=1.,
                    head_names=['JF_action_minus_B','JM_action_minus_B','qualification']+(['motion_worst_ratio_minus_1'] if have_margin else []))
            return dict(schema='v8.c3b.frozen_relative_recipe.v1',actions=ACTIONS,recipe_hashes=recipe_hashes,
                history_feature_names=names,commissioned25_feature_names=commissioned_names,models=models,
                source_shared_dataset_sha256=EXPECTED,source_history_dataset_sha256=sha(HERE/'V7_COMPLETE_B_HISTORY8_DATASET.json'),
                original_gates_unchanged=True,context_scope='ALL_EXPOSED_DEVELOPMENT',
                inference_scope='COLD_REPLAY_NOT_CONTINUOUS_TRIAL_ADAPTATION')
        def realized(g,a):
            label=outcomes[g][a];base=outcomes[g][0]
            return dict(selected_tag=ACTIONS[a],source_result_id=matched[g][a]['id'],
                original_qualified=label['original_qualified'],JF_N_s=label['JF_N_s'],JM_Nm_s=label['JM_Nm_s'],
                JF_gain_vs_B_N_s=base['JF_N_s']-label['JF_N_s'],
                JM_gain_vs_B_Nm_s=base['JM_Nm_s']-label['JM_Nm_s'],
                motion_worst_ratio=label.get('motion_worst_ratio'),
                motion_failed_requirements=label['motion_failed_requirements'],
                native_metrics_evaluation_only=label.get('native_metrics'),
                qualified_force_ranking_eligible=bool(label['original_qualified']))
        for g in range(6):
            train=[j for j in range(6) if j!=g];snapshot=snapshot_for(train)
            snapshots.append(dict(left_out=groups[g],snapshot=snapshot));models={}
            for name in KINDS+['HISTORY_DISABLED']:
                pred=select(snapshot,history=None if name in ['ACTION_ONLY','HISTORY_DISABLED','COMMISSIONED25_INTERACTION'] else history[g],
                            commissioned25=C[g].tolist() if name=='COMMISSIONED25_INTERACTION' else None,model_id=name)
                models[name]=dict(prediction=pred,realized=realized(g,pred['selected_index']))
            constant=best_constant(train,outcomes);stump=stump_fit(train,H,outcomes)
            stump_a=stump.get('constant_action')
            if stump_a is None:stump_a=stump['left_action'] if H[g,stump['feature_index']]<=stump['threshold'] else stump['right_action']
            fixed={a:realized(g,i) for i,a in enumerate(ACTIONS)}
            fold_results.append(dict(group=groups[g],split='EXPOSED_CONTEXT_LOCO_DEVELOPMENT_NOT_INDEPENDENT_TEST',
                models=models,baselines=dict(fixed_recipes=fixed,training_best_constant=realized(g,constant),
                    training_history_stump=dict(model=stump,realized=realized(g,stump_a)))))
        full=snapshot_for(list(range(6)));full['frozen_unix']=time.time()
        write(out/'FROZEN_FULL_SNAPSHOT.json',full)
        write(out/'LOCO_SNAPSHOTS.json',dict(rows=snapshots))
        write(out/'LOCO_PREDICTIONS_AND_REALIZED.json',dict(rows=fold_results))
        full_results=[]
        for g in range(6):
            entries={}
            for name in KINDS+['HISTORY_DISABLED']:
                pred=select(full,history=None if name in ['ACTION_ONLY','HISTORY_DISABLED','COMMISSIONED25_INTERACTION'] else history[g],
                            commissioned25=C[g].tolist() if name=='COMMISSIONED25_INTERACTION' else None,model_id=name)
                entries[name]=dict(prediction=pred,realized=realized(g,pred['selected_index']))
            full_results.append(dict(group=groups[g],models=entries))
        write(out/'FULL_EXPOSED_FIT_PREDICTIONS.json',dict(rows=full_results))
        aggregate={}
        for name in KINDS+['HISTORY_DISABLED']:
            rr=[r['models'][name]['realized'] for r in fold_results]
            aggregate[name]=dict(actions=[r['selected_tag'] for r in rr],qualified=sum(r['original_qualified'] for r in rr),
                total=6,qualified_JF_gain_sum_vs_B=sum(r['JF_gain_vs_B_N_s'] for r in rr if r['original_qualified']),
                unqualified_JF_not_ranked=[dict(group=groups[i],JF_N_s=r['JF_N_s'],motion_failed=r['motion_failed_requirements'])
                                          for i,r in enumerate(rr) if not r['original_qualified']])
        result=dict(status='COMPLETED_APPROVED_OFFLINE_FIT',aggregate_LOCO=aggregate,
            ridge_solve_count=solves,head_count=Y.shape[-1],context_count=6,complete_outcome_rows=18,
            new_independent_patients=0,independent_test_count=0,new_physics=0,
            source_histories_have_full_integral_closure=True,
            margin_head_status='FIT_FROM_ORIGINAL_LABELS' if have_margin else 'NOT_AVAILABLE_NOT_FILLED',
            frozen_snapshot_sha256=sha(out/'FROZEN_FULL_SNAPSHOT.json'),
            dataset_manifest_sha256=sha(out/'DATASET_SOURCE_MANIFEST.json'),
            source_shared_dataset_sha256=EXPECTED,source_history_dataset_sha256=sha(HERE/'V7_COMPLETE_B_HISTORY8_DATASET.json'),
            started_unix=started,finished_unix=time.time(),process_cpu_s=time.process_time()-cpu,
            max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            limitations=['all contexts exposed development','LOCO contexts not guaranteed independent patients',
                'history is completed same-cold-parent B counterfactual, not actual persistent Trial1-to2',
                'ridge qualification scores not calibrated probabilities','fixed menu three recipes only'])
        write(out/'RESULTS.json',result)
        write(out/'END.json',dict(status='SUCCESS',finished_unix=time.time(),pid=os.getpid(),all_computation_foreground=True))
        print(json.dumps({k:result[k] for k in ['status','ridge_solve_count','aggregate_LOCO','frozen_snapshot_sha256','process_cpu_s']},ensure_ascii=False))
    except BaseException as e:
        write(out/'FAILURE.json',dict(error=str(e),finished_unix=time.time(),process_cpu_s=time.process_time()-cpu,new_physics=0))
        raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
