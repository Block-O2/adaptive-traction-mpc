from freeze import *
import numpy as np
import sys
def main():
 old=json.loads((LOCAL.parent/'expert_strength_value_adequacy_v1/output/E_RICH_DIFF_BEST.json').read_text())
 table=np.asarray(old['table']).reshape(2,5,3);name=sys.argv[1] if len(sys.argv)>1 else '002_K3_model_probe'
 save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='probe',table=table.tolist(),result_path=str(STUDY/'output'/(name+'_RESULT.json')),historical_table_source_sha256=sha(LOCAL.parent/'expert_strength_value_adequacy_v1/output/E_RICH_DIFF_BEST.json'),table_role='zero-learning nonzero regression/design reference; old data not training labels'))
 save(STUDY/'output/HISTORICAL_K3_DESIGN_REFERENCE.json',dict(table=table.tolist(),old_J_F=old['J_F'],no_cross_information_numeric_ranking=True,source_sha256=sha(LOCAL.parent/'expert_strength_value_adequacy_v1/output/E_RICH_DIFF_BEST.json')))
 print(name)
if __name__=='__main__':main()
