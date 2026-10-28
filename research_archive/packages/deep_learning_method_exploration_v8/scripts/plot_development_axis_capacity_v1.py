"""One descriptive standalone figure from two closed exposed-development grids."""
from pathlib import Path
import hashlib
import json
import math
import os
import resource
import time

os.environ['MPLBACKEND'] = 'Agg'
os.environ['MPLCONFIGDIR'] = '/tmp/v8_mpl_capacity'
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parents[1]
GROUPS = [('V8DEVCAP01H', 'Old development: heavy035'), ('V8DEVCAP01L', 'Old development: light065')]
GRID = [('AXIS_L0', 0.0), ('AXIS_L025', .25), ('AXIS_L05', .5), ('AXIS_L075', .75), ('AXIS_L1_REPEAT', 1.0)]


def main():
    started, cpu = time.perf_counter(), time.process_time()
    refs, cases = {}, []

    def read(rel):
        raw = (P / rel).read_bytes()
        refs[rel] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    for group, title in GROUPS:
        end = read('owned/' + group + '_SUPERVISOR_END.json')
        assert end['state'] == 'STOP' and not end['survivors']
        final = read('analysis/' + group + '_DEV_CAPACITY_FINAL.json')
        assert final['counts']['pure_map_returned'] == 5
        assert final['counts']['model_initialize_restore_forward_score_fit_RNG_sampling'] == 0
        baseline = read('attempts/' + group + '_B_RESULT.json')
        assert baseline['complete'] is True and baseline['qualified'] is True
        points = []
        for tag, lam in GRID:
            rel = 'attempts/' + group + '_' + tag + '_RESULT.json'
            if tag not in final['completed']:
                assert tag in final['NOT_RUN']
                points.append(dict(tag=tag, lam=lam, status='NOT_RUN', complete=None, qualified=None))
                continue
            row = read(rel)
            replay = read('audit/scorer_replay/' + group + '_' + tag + '.json')
            assert replay['original_result_exact_reproduced'] is True and not replay['errors']
            full = row['complete'] is True
            if full:
                assert all(isinstance(row[k], (int, float)) and math.isfinite(row[k]) for k in ['JF', 'JM'])
                assert replay['qualified_replay'] is row['qualified']
            points.append(dict(tag=tag, lam=lam, status='COMPLETE' if full else 'PARTIAL_NOT_RANKED',
                               complete=row['complete'], qualified=row['qualified'],
                               JF=row['JF'] if full else None, JM=row['JM'] if full else None,
                               failed_requirements=(row.get('motion_vs_B') or {}).get('failed_requirements')))
        gate = read('audit/' + group + '_AXIS_L1_REPEAT_REPEAT_GATE.json')
        assert gate['status'] == 'PASS'
        cases.append(dict(group=group, title=title, baseline={k:baseline[k] for k in ['JF', 'JM']},
                          points=points, original_H_lambda1_raw_gate='PASS',
                          NOT_RUN=final['NOT_RUN'], stop=final['stop']))
    stem = P / 'figures/DEVELOPMENT_FIXED_AXIS_CAPACITY_V1'
    assert not stem.with_suffix('.png').exists() and not stem.with_suffix('.json').exists()
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for i, case in enumerate(cases):
        missing = []
        for j, (metric, label) in enumerate([('JF', 'JF (N s)'), ('JM', 'JM (N m s)')]):
            ax = axs[i, j]
            ax.axhline(case['baseline'][metric], color='#303030', ls='--', lw=1.2, label='Original B (outside lambda axis)')
            used = set()
            for point in case['points']:
                if point['complete'] is not True:
                    if j == 0:
                        missing.append('lambda ' + str(point['lam']) + ': ' + point['status'])
                    continue
                qualified = point['qualified'] is True
                legend = 'Complete, qualified' if qualified else 'Complete, motion failed'
                ax.scatter(point['lam'], point[metric], marker='o' if qualified else 'x',
                           color='#117864' if qualified else '#b03a2e', s=70, linewidths=1.8,
                           label=legend if legend not in used else None, zorder=3)
                used.add(legend)
            ax.set_xticks([0, .25, .5, .75, 1]); ax.set_xlim(-.06, 1.06)
            ax.set_xlabel('Fixed lambda (lambda 0 is not B)'); ax.set_ylabel(label)
            ax.set_title(case['title'] + ' | ' + metric)
            ax.grid(alpha=.16); ax.legend(loc='best', fontsize=8)
            if missing:
                ax.text(.02, .03, '\n'.join(missing), transform=ax.transAxes, fontsize=8, color='#555555')
    fig.suptitle('Exposed development fixed-axis capability: original TASK and motion gates', fontsize=13)
    fig.supxlabel('Five registered grid points; no interpolation or uncertainty claim. Lambda 1 is a paid full-raw H150 repeat.\nUnqualified costs are descriptive; partial/NOT_RUN costs are omitted. These are not new independent validation conditions.', fontsize=9)
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(stem.with_suffix('.' + ext), dpi=180 if ext == 'png' else None)
    plt.close(fig)
    manifest = dict(status='CLOSED_DESCRIPTIVE_FIGURE_NOT_FEASIBLE_RANK_OR_GENERALIZATION',
                    created_unix=time.time(), inputs_sha256=refs, cases=cases,
                    outputs={ext:dict(path=str(stem.with_suffix('.' + ext).relative_to(P)),
                                      sha256=hashlib.sha256(stem.with_suffix('.' + ext).read_bytes()).hexdigest()) for ext in ['png', 'pdf', 'svg']},
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    new_model_fit_scorer_raw_physics_calls=0,
                    resources=dict(wall_s=time.perf_counter()-started, CPU_s=time.process_time()-cpu,
                                   RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                   scope='figure core; external launcher/startup cost remains separate'))
    with stem.with_suffix('.json').open('x') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=manifest['status'], resources=manifest['resources'])))


if __name__ == '__main__':
    main()
