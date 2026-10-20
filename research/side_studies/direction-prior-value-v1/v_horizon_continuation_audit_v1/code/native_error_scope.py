from audit_common import *
from collections import Counter
def main():
 rows=read(STUDY/'ACTUAL_NATIVE_VALUE_PREDICTION_ERRORS.json')['rows'];splits=Counter(read(r['source'])['split'] for r in rows);files=Counter(r['source'] for r in rows)
 print(dict(rows=len(rows),split_counts=dict(splits),files=len(files),sample_names=list(files)[:8]))
 data=read(STUDY/'SCORE_DECOMPOSITION.json');s=data['states'][-1];print(s['state'],[dict(index=r['index'],costs=r['mode_costs'],P=r['P_score'],PV=r['PV_score'],delta=r['DeltaV']) for r in s['rows']])
if __name__=='__main__':main()
