"""Post-fit read-only diagnostic and plots. No gradient, training, or simulation."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def run():
    check_lock(); assert read('STATE.json')['status']=='BC_REPRESENTATION_FIT_FAILED'
    z=np.load(DEMO);obs=z['observations'];target=z['actions'];phases=z['phase'];times=z['task_s']
    data=read('OFFLINE_RESULTS.json'); diagnostics=[]
    unique=len(np.unique(obs,axis=0));jump=np.linalg.norm(np.diff(target,axis=0),axis=1)
    outbound_adjacent=(phases[1:]=='OUTBOUND')&(phases[:-1]=='OUTBOUND')
    largest=int(np.argmax(np.where(outbound_adjacent,jump,-1)))+1
    pair=dict(before_index=largest-1,after_index=largest,before_time_s=float(times[largest-1]),after_time_s=float(times[largest]),
              before_action=target[largest-1].tolist(),after_action=target[largest].tolist(),
              observation_L2=float(np.linalg.norm(obs[largest]-obs[largest-1])),action_L2=float(jump[largest-1]),
              knee_target_jump_deg=float((target[largest,1]-target[largest-1,1])*62.5),phase=str(phases[largest]))
    fig,axes=plt.subplots(1,3,figsize=(14,4.2),constrained_layout=True)
    af,aa=plt.subplots(3,2,figsize=(12,10),constrained_layout=True)
    for row,ax,axs in zip(data,axes,aa):
        seed=row['seed'];p=np.load(L/f'EXACT_TEACHER_PREDICTIONS_seed_{seed}.npz');error=p['error'].astype(float)
        pred=p['actor_actions'];sse=np.sum(error**2,axis=1);worst=int(np.argmax(np.max(np.abs(error),axis=1)))
        top=np.argsort(sse)[-10:][::-1]
        other=np.arange(len(obs))!=worst
        diagnostic=dict(seed=seed,worst_index=worst,worst_phase=str(phases[worst]),worst_task_s=float(times[worst]),
             teacher_action=target[worst],actor_action=pred[worst],worst_abs_error=float(np.max(np.abs(error[worst]))),
             worst_target_error_deg=np.abs(error[worst])*62.5,worst_sample_SSE_fraction=float(sse[worst]/sse.sum()),
             worst_sample_in_training=bool(worst in p['train_indices']),
             RMSE_without_worst_sample_diagnostic_only=float(np.sqrt(np.mean(error[other]**2))),
             top_errors=[dict(index=int(i),phase=str(phases[i]),task_s=float(times[i]),raw_teacher_action=target[i],raw_actor_action=pred[i],max_abs_error=float(np.max(np.abs(error[i]))),training_sample=bool(i in p['train_indices'])) for i in top],
             gate_uses_all_593_samples=True,no_outlier_exclusion_or_retraining=True)
        diagnostics.append(diagnostic)
        curve=read(f'LOSS_CURVE_seed_{seed}.json');epochs=np.array([r['epoch'] for r in curve])
        for key,label in [('train_balanced_MSE','train balanced'),('validation_balanced_MSE','validation balanced'),('full_MSE','all samples')]:
            ax.semilogy(epochs,[r[key] for r in curve],label=label,lw=1.2)
        ax.axvline(row['best_epoch'],ls=':',color='black',label='selected epoch')
        ax.set_title(f'Seed {seed} / {row["stop_reason"]}');ax.set_xlabel('Epoch');ax.set_ylabel('Raw action MSE');ax.grid(alpha=.2);ax.legend(fontsize=8)
        for j,label in enumerate(('hip','knee')):axs[0].plot(times,np.abs(error[:,j])*62.5,label=label,lw=1)
        axs[0].axvline(times[worst],ls=':',color='black');axs[0].set_title(f'Seed {seed}: ALL 593 teacher states');axs[0].set_ylabel('Absolute target error (deg)');axs[0].set_xlabel('Task time (s)');axs[0].legend();axs[0].grid(alpha=.2)
        region=(times>=1.1)&(times<=1.85)
        axs[1].plot(times[region],(target[region,1]+1)*62.5,'k.-',label='teacher knee',lw=1)
        axs[1].plot(times[region],(pred[region,1]+1)*62.5,'.-',label='BC knee',lw=1)
        axs[1].axvline(times[largest],ls=':',color='gray');axs[1].set_title('OUTBOUND knee-release discontinuity');axs[1].set_xlabel('Task time (s)');axs[1].set_ylabel('Absolute knee target (deg)');axs[1].grid(alpha=.2);axs[1].legend()
    fig.suptitle('Frozen actor-only BC: loss curves (no closed-loop tuning)');af.suptitle('Offline reproduction failure: sparse knee-action switch')
    for figure,name in ((fig,'LOSS_CURVES.png'),(af,'OFFLINE_ACTION_ERROR.png')):
        for folder in (L,D):figure.savefig(folder/name,dpi=150)
        plt.close(figure)
    result=dict(status='POST_FIT_READ_ONLY_AUDIT',source_sha256=sha(Path(__file__)),teacher_unique_observation_count=unique,
                exact_duplicate_observations=593-unique,largest_adjacent_OUTBOUND_teacher_action_jump=pair,seeds=diagnostics,
                inference='All selected checkpoints smooth the isolated OUTBOUND knee release instead of fitting its abrupt target jump. Validation interleaving excludes the release sample itself while including its preceding neighbor. The selected validation-optimal checkpoint therefore need not minimize complete training-set or worst-case error. This is a registered supervised-fit failure; capacity impossibility and partial observability are not established.',
                formal_training_or_closed_loop_started=False,thresholds_or_models_changed=False)
    save('POST_FIT_OFFLINE_AUDIT.json',result)
    summary=read('SUMMARY.json')
    summary['SCIENTIFIC_INTERPRETATION']=[
        'Teacher all-593-transition same-wrapper reproduction is independently VALID; normalization and native action transform checks pass.',
        'All three selected BC checkpoints miss the OUTBOUND knee-release jump at 1.505 s; this is the dominant offline error and BC closed-loop was not attempted.',
        'The preregistered fit gate failed. Sparse switch sampling/validation selection contributes; this run does not establish architecture impossibility or observation insufficiency.']
    summary['scientific_interpretation']=summary.pop('SCIENTIFIC_INTERPRETATION')
    summary['NEXT']='Prioritize an offline observation/action/network fit audit of the 1.505 s knee-release switch and checkpoint-selection sensitivity; no longer SAC run.'
    summary['POST_FIT_OFFLINE_AUDIT']=dict(path=str(D/'POST_FIT_OFFLINE_AUDIT.json'),worst_teacher_state_index=largest)
    summary['CLOSED_LOOP'].update(seed_success_count=None,formal_evaluations_run=0,VALID=None,reason='Offline gate failed; closed loop not evaluated')
    summary['REPORT_PATH']=str(W/NAME/'output/BC_REPRODUCTION_GATE_V1_REPORT.md')
    save('SUMMARY.json',summary)
    report=(D/'BC_REPRODUCTION_GATE_V1_REPORT.md').read_text()
    old_start='The independent frozen evaluator consumed recorded physical outputs only after the episode.'
    start=report.index(old_start if old_start in report else 'No autonomous BC physics evaluation was run.')
    end=report.index('\n## Independent replay and valid-only force characterization',start)
    diagnostic_text=['No autonomous BC physics evaluation was run. Its settled OUTBOUND/HOLD/RETURN, progress and VALID fields are **not evaluated**, not zero-success results. The only physical rollout in this experiment is the teacher revalidation.',
        '\n## Offline error diagnosis',f'\nThe largest adjacent OUTBOUND teacher knee-target jump occurs between sample {largest-1} ({times[largest-1]:.3f} s) and sample {largest} ({times[largest]:.3f} s): {pair["before_action"][1]:.8f} -> {pair["after_action"][1]:.8f} raw action, or {pair["knee_target_jump_deg"]:.3f} degrees. Normalized observation L2 across those two states is {pair["observation_L2"]:.8f}; all {unique} stored observations are distinct.',
        '\n|Seed|Worst sample|Knee error (deg)|Fraction of total squared error|RMSE excluding that sample (diagnostic only)|',
        '|---|---|---|---|---|']
    for d in diagnostics:diagnostic_text.append(f'|{d["seed"]}|{d["worst_index"]} at {d["worst_task_s"]:.3f}s|{d["worst_target_error_deg"][1]:.4f}|{d["worst_sample_SSE_fraction"]:.2%}|{d["RMSE_without_worst_sample_diagnostic_only"]:.8f}|')
    diagnostic_text += ['\nThe large-error switch sample is in training for all seeds. Its preceding sample is in validation under the preregistered every-fifth interleaving. The recorded validation-selected checkpoints smooth the action discontinuity. Previous-action features change on the following observation; simply reproducing that history performs well away from the one-off switch. This pattern warrants checking rare switch coverage and selection behavior before claiming an intrinsic actor capacity limit.',
        '\nClassification A applies to the **selected checkpoints under this fixed supervised procedure**, not a proof that the network cannot express the teacher mapping. No identical-observation conflicting label pair was found. C (partial observability) and D (absolute-target sensitivity) are unproven. E (normalization/action-transform mismatch) is checked by fixed-scale schema and native forward/predict identity; teacher same-wrapper all-transition exact reproduction checks the baseline F (wrapper/action realization) route. Student off-trajectory action realization has not been tested.',
        '\nNo sample was removed from formal metrics or the gate. The diagnostic RMSE after removing the single worst sample is only a concentration statistic. No additional training, model selection, threshold change, closed-loop run or hyperparameter revision followed this audit.',
        '\n![Loss curves](LOSS_CURVES.png)\n\n![Offline action errors](OFFLINE_ACTION_ERROR.png)\n']
    report=report[:start]+'\n'.join(diagnostic_text)+report[end:]
    start=report.index('## Scientific interpretation');end=report.index('\n## Preservation and checks',start)
    report=report[:start]+'## Scientific interpretation\n\n'+'\n'.join('- '+x for x in summary['scientific_interpretation'])+'\n'+report[end:]
    report=report.replace('Only newly generated high-frequency evidence was pruned under the predeclared retention policy; all per-seed compact traces and metrics remain.',
                          'Only the new teacher high-frequency trace/runtime archive is retained; there were no BC physical traces to prune. Per-seed offline prediction arrays, loss curves, plots, metrics and checkpoints remain.')
    report=report.replace('Commands: launch.sh (preflight.py, teacher.py, train.py, three evaluate.py formal processes, diagnose.py, optional one evaluate.py confirmation process, finish.py).',
                          'Commands actually executed: launch.sh -> preflight.py, teacher.py, train.py, finish.py. The closed-loop branch of launch.sh remained closed. The later offline_audit.py performs read-only numeric diagnosis and plotting; its source hash is recorded in POST_FIT_OFFLINE_AUDIT.json.')
    report=report.replace('Study observation/network/action representation and offline approximation error.',summary['NEXT'])
    prose('BC_REPRODUCTION_GATE_V1_REPORT.md',report)
    # Artifact hashes supplement the frozen experiment source lock; no production source is edited.
    artifacts={str(p.relative_to(L)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in L.iterdir() if p.is_file() and p.name not in ('ARTIFACT_MANIFEST.json','FORMAL_RUN.log','STATE.json')}
    save('ARTIFACT_MANIFEST.json',artifacts);check_lock()
    print(json.dumps(clean(dict(status='POST_FIT_AUDIT_COMPLETE_STOP',worst_sample=largest,teacher_jump=pair,seeds=[{k:d[k] for k in ('seed','worst_task_s','worst_abs_error','worst_sample_SSE_fraction')} for d in diagnostics]))),flush=True)

if __name__=='__main__':run()
