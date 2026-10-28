"""Actual finite-menu rank variation; no new training or outcome-based selection."""
from pathlib import Path
import json,time,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
P=Path(__file__).resolve().parents[1]
from v6_prescreen import canonical
def main():
    menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu']
    library=json.loads((P/'freeze/LIBRARY.json').read_text())['library'];rows=[]
    groups=json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups']+['TEST_O1','TEST_O2','TEST_R1','TEST_R2','SCREEN_AUDIT']
    for g in groups:
        f=P/'data'/f'{g}.json'
        if not f.exists():continue
        cfg=json.loads((P/'experiments'/f'{g}.json').read_text());phase=cfg['fork_phase'];data=[r for r in json.loads(f.read_text()) if r['horizon_s']==.5 and r['tag'] in menu]
        unique={};aliases={}
        for r in data:
            key=canonical(library[r['tag']],phase)
            if key in unique:aliases[r['tag']]=unique[key]['tag']
            else:unique[key]=r
        qualified=sorted([r for r in unique.values() if r['qualified']],key=lambda r:r['labels']['full_remaining_JF'])
        rows.append(dict(group=g,phase=phase,upstream=cfg.get('upstream_policy','ORIGINAL_B_PREFIX'),
            role='frozen test' if g.startswith('TEST_') or g=='SCREEN_AUDIT' else 'development',
            aliases=aliases,qualified_order=[r['tag'] for r in qualified],
            full_remaining_JF={r['tag']:r['labels']['full_remaining_JF'] for r in unique.values()},
            all_unique_original_qualified=all(r['qualified'] for r in unique.values()),
            best_to_second_JF_gap=None if len(qualified)<2 else qualified[1]['labels']['full_remaining_JF']-qualified[0]['labels']['full_remaining_JF']))
    bydomain={}
    for r in rows:
        key=r['phase']+'|'+r['upstream'];bydomain.setdefault(key,[]).append(r)
    domains=[]
    for key,rr in bydomain.items():
        orders={tuple(r['qualified_order']) for r in rr if r['all_unique_original_qualified']}
        domains.append(dict(domain=key,states=len(rr),complete_qualified_states=sum(r['all_unique_original_qualified'] for r in rr),
            distinct_complete_qualified_orders=[list(x) for x in sorted(orders)],
            actual_within_phase_upstream_order_variation=len(orders)>1,
            empty_qualified_menus=[r['group'] for r in rr if not r['qualified_order']]))
    out=dict(evaluated_unix=time.time(),rows=rows,domains=domains,
        scope='Actual qualified finite-menu order under each fixed phase/upstream contract. '
        'Qualification is used for retrospective audit, not a deployed future mask. '
        'Between-phase differences alone are solved by a transparent phase rule and do not establish individualized learning value. '
        'No additional independent states are claimed for repeated menu branches.')
    (P/'analysis/ACTUAL_ACTION_RANK_VARIATION.json').write_text(json.dumps(out,indent=2)+'\n')
    print('RANK_VARIATION',[(r['domain'],r['actual_within_phase_upstream_order_variation']) for r in domains],flush=True)
if __name__=='__main__':main()
