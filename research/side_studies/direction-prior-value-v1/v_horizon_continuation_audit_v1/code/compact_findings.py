from audit_common import *
def main():
 for name in ('AUDIT_CONTRACT.json','MAIN_SOURCES_BEFORE.json','SOURCE_SEMANTICS.json','INACTIVE_PENDING_SENSITIVITY.json','EVENT_CLOCK_ALIGNMENT.json'):
  d=read(STUDY/name);print(name,'top',list(d) if isinstance(d,dict) else str(d)[:1000])
  if name=='AUDIT_CONTRACT.json':print('other',{k:v for k,v in d.items() if k!='cases'})
  if name=='SOURCE_SEMANTICS.json':print(d)
 for p in list((STUDY/'output').glob('*_RESULT.json'))[:3]:
  d=read(p);print(p.name,'keys',list(d),'metrickeys',list(d.get('metric',{})));print('countfields',{k:v for k,v in d.get('metric',{}).items() if 'step' in k or 'api_call' in k or 'duration' in k or 'dt_' in k})
 for s in read(STUDY/'SCORE_DECOMPOSITION.json')['states']:
  print('state',s['state']);print('costs',[(r['index'],r['mode_costs'],r.get('PV_committed_score_error')) for r in s['rows']])
 print('value error',{k:v for k,v in read(STUDY/'ACTUAL_NATIVE_VALUE_PREDICTION_ERRORS.json').items() if k!='rows'})
if __name__=='__main__':main()
