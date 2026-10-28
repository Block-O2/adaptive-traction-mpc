"""Export closed-data scientific figures; zero fitting and zero physics."""
from pathlib import Path
import hashlib
import json
import os

P = Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR'] = str(P / 'runtime/tmp/mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    source = P / 'analysis/FROZEN_TRANSFER_COMPARISON_V1.json'
    data = json.loads(source.read_text())
    destination = P / 'figures'
    destination.mkdir(exist_ok=True)
    names = ['B', 'LATE_H150', 'EARLY_H150', 'LATE_PHASE', 'EARLY_PHASE']
    colors = ['#475569', '#0072B2', '#009E73', '#D55E00', '#CC79A7']
    labels = ['B', 'Late H150', 'Early H150', 'Late phase', 'Early phase']
    titles = ['CTX01: long segments', 'CTX02: mixed', 'CTX03: up2xplus', 'CTX04: up4xminus']
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'font.family': 'DejaVu Sans', 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.8), sharex=True, sharey=True)
    for axis, context, title in zip(axes.flat, data['contexts'], titles):
        rows = [r for r in data['menu_outcomes'] if r['group'] == context['group']]
        for tag, color in zip(names, colors):
            row = next(r for r in rows if r['tag'] == tag)
            axis.scatter(row['delta_JF_vs_B'], row['delta_JM_vs_B'], color=color,
                         marker='o' if row['qualified'] else 'X', s=68,
                         edgecolor='white', linewidth=.6, zorder=3)
        axis.axvline(0, color='#94a3b8', linewidth=.7)
        axis.axhline(0, color='#94a3b8', linewidth=.7)
        axis.grid(alpha=.17)
        axis.set_title(title, loc='left', fontsize=11)
        axis.set_xlim(-48, 4)
        axis.set_ylim(-.5, 8)
    for axis in axes[1]:
        axis.set_xlabel(r'$\Delta J_F$ versus same-state B (N s)')
    for axis in axes[:, 0]:
        axis.set_ylabel(r'$\Delta J_M$ versus same-state B (N m s)')
    handles = [plt.Line2D([], [], color=c, marker='o', linestyle='', label=l)
               for c, l in zip(colors, labels)]
    handles.append(plt.Line2D([], [], color='#334155', marker='X', linestyle='',
                              label='Original motion qualification failed'))
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, .025),
               ncol=3, frameon=False, fontsize=9)
    fig.suptitle('Frozen five-recipe transfer: force reduction and moment cost', y=.995, fontsize=13)
    fig.text(.5, .002, 'Complete original tasks. Failed motion points remain visible and are excluded from qualified benefit claims.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .14, 1, .965))
    outputs = {}
    for extension in ['png', 'pdf', 'svg']:
        path = destination / ('FROZEN_TRANSFER_FORCE_MOMENT_V1.' + extension)
        assert not path.exists()
        fig.savefig(path, dpi=220, bbox_inches='tight')
        outputs[str(path.relative_to(P))] = hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    record = {'source': str(source.relative_to(P)),
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'outputs_sha256': outputs, 'matplotlib_version': matplotlib.__version__,
              'fit': 0, 'physics': 0, 'points': 20, 'original_qualification_preserved': True}
    with (destination / 'FROZEN_TRANSFER_FORCE_MOMENT_V1_MANIFEST.json').open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': 'EXPORTED_CLOSED_DATA_ONLY', 'outputs': list(outputs)}))


if __name__ == '__main__':
    main()
