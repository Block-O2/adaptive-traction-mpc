"""Exposed representative-state attribution, permanently outside fitting."""
from task_bootstrap import *
import numpy as np

def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1'
 contract=json.loads((STUDY/('DIAGNOSTIC_CONTRACT_'+version+'.json')).read_text())
 source=json.loads((STUDY/'output'/(contract['source']+'_RESULT.json')).read_text())
 rows=[]
 for phase,index in contract['targets']:
  label=version+'_committed_attribution_'+phase+'_'+str(index)
  pred=json.loads((STUDY/'output'/(label+'_OFFLINE_PREDICTIONS.json')).read_text());outcomes=[]
  for j,p in enumerate(pred['rows']):
   files=sorted((STUDY/'output').glob(label+'_candidate'+str(j)+'*_DATA.json'))
   if not files:
    outcomes.append(dict(candidate=j,source=p['source'],Q=p['Q'],S=p.get('S'),native_feasible=p.get('feasible'),native_proposal_accepted=p.get('proposal_accepted'),valid=False,status='NO_SUCCESS_LABEL',reason='preserved branch failure; see attempt/error evidence'));continue
   d=json.loads(files[-1].read_text());m=d['metric']
   outcomes.append(dict(candidate=j,source=p['source'],Q=p['Q'],S=p.get('S'),native_feasible=p.get('feasible'),native_proposal_accepted=p.get('proposal_accepted'),valid=bool(m['valid']),status=m['status'],remaining_J_F=d['remaining_J_F'],full_J_F=m['J_F'],moment=m['moment_integral'],prefix_J_F=d['child']['start_J_F'],plan=d['table'],data_sha256=sha(files[-1])))
  feasible=[r for r in outcomes if r['valid']]
  ordinary=[r for r in feasible if r['candidate']<6];generated=[r for r in feasible if r['candidate']>=6]
  best=min(feasible,key=lambda r:r['remaining_J_F']) if feasible else None
  # Selection uses only the causal native certificate, never knowledge of
  # future task validity. Invalid selected outcomes are harmful, not removed.
  selectable=[r for r in outcomes if r.get('native_feasible') and r.get('native_proposal_accepted')]
  q=min(selectable,key=lambda r:r['Q']) if selectable else None
  s=min(selectable,key=lambda r:r['S']) if selectable else None
  selected=next((r for r in feasible if r['candidate']==pred['original_selected_index']),None)
  prefix=feasible[0]['prefix_J_F'] if feasible else None
  rows.append(dict(phase=phase,index=index,causal_context_equal=pred['causal_context_equal'],outcomes=outcomes,valid_count=len(feasible),actual_best_candidate=None if best is None else best['candidate'],Q_top1_candidate=None if q is None else q['candidate'],Q_top1_valid=None if q is None else q['valid'],Q_top1_regret=None if q is None or best is None or not q['valid'] else q['remaining_J_F']-best['remaining_J_F'],S_top1_candidate=None if s is None else s['candidate'],S_top1_valid=None if s is None else s['valid'],S_top1_regret=None if s is None or best is None or not s['valid'] else s['remaining_J_F']-best['remaining_J_F'],Q_harmful_top1=None if q is None else (not q['valid'] or (best is not None and q['remaining_J_F']>best['remaining_J_F']+1e-6)),G_best_remaining_J_F=min([r['remaining_J_F'] for r in generated]) if generated else None,ordinary_best_remaining_J_F=min([r['remaining_J_F'] for r in ordinary]) if ordinary else None,G_best_improvement_over_ordinary=None if not ordinary or not generated else min(r['remaining_J_F'] for r in ordinary)-min(r['remaining_J_F'] for r in generated),original_selected_committed_remaining_J_F=None if selected is None else selected['remaining_J_F'],original_rolling_remaining_J_F=None if prefix is None else source['metric']['J_F']-prefix,continuation_difference_N_s=None if selected is None else selected['remaining_J_F']-(source['metric']['J_F']-prefix),original_selected_index=pred['original_selected_index']))
 gate=STUDY/'output'/('060_'+version+'_committed_attribution_REPLAY_GATE.json')
 assert gate.exists() and json.loads(gate.read_text())['status']=='PASS','EXACT_REPLAY_REQUIRED'
 out=dict(version=version,rows=rows,source=contract['source'],replay_gate=json.loads(gate.read_text()),never_training=True,not_independent_test=True,interpretation='Q predicts committed native-certified suffix; rolling selection revises future plans and can differ. All invalid short outcomes stay unranked. G union is an offline diagnostic only, not a larger online candidate budget.')
 save(STUDY/('DIAGNOSTIC_ANALYSIS_'+version+'.json'),out)
 print(json.dumps([{k:r[k] for k in ('phase','index','valid_count','Q_top1_regret','G_best_improvement_over_ordinary','continuation_difference_N_s')} for r in rows]))
if __name__=='__main__':main()
