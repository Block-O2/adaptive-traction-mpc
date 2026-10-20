from common import *
j=load(MATRIX/'DIAGNOSTIC_ANALYSIS_v1.json')
print('DIAGNOSTIC', [{k:v for k,v in r.items() if k!='outcomes'} for r in j['rows']])
r=load(MATRIX/'output'/(j['source']+'_RESULT.json'));print('original inputs',r['inputs']);print('qual',r['metric']['physical_audit']['unchanged_evaluator']['execution_mode'])
q=load(OUT/'PACKAGE_VERIFICATION.json');print('phasecount',next(r for r in q['checks'] if r['name']=='phase_coverage'))
rows=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json')['historical_rows'];print('modelhashes',len(set(r['model_hash'] for r in rows)),'betas',len(set(tuple(r['model_beta']) for r in rows)))
