from freeze import *
def main():
 out=STUDY/'output';name='007_P_timing_regression';metric=json.loads((out/(name+'.json')).read_text());search=json.loads((out/(name+'_SEARCH.json')).read_text());print(json.dumps(dict(valid=metric['valid'],phase_durations=metric['phase_durations'],calls=search['full_model_inverse_dynamics_calls'],model_wall=search['model_wall_s'])))
 for r in search['rows']:
  selected=[c for c in r['candidates'] if not c['rejected'] and c['source']==r['selected_source'] and c['plan']==r['selected_plan']];picked=min(selected,key=lambda c:c['score']) if selected else None;baselines=[c for c in r['candidates'] if c['source'] in ('B','remaining_plan','qualified_unlearned_K3_seed')]
  def compact(c):return {k:c.get(k) for k in ('source','score','rejected','reason')}|dict(arrival=c.get('prediction',{}).get('predicted_phase_arrival_elapsed_s'),durations=c.get('prediction',{}).get('predicted_durations'))
  print(json.dumps(dict(phase=r['context']['phase'],task_s=r['context']['task_s'],phase_s=r['context']['observation'][47]*10,counts=r['count_before'],picked=None if picked is None else compact(picked),baselines=[compact(c) for c in baselines[:2]])))
if __name__=='__main__':main()
