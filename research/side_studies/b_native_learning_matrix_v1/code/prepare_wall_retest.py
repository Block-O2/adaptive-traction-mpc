from task_bootstrap import *
from prepare import enqueue
for method in ('M0','M2'):
 req=json.loads((STUDY/'queue'/('070_v1_wall_'+method+'.json')).read_text());req.pop('id');req.pop('result_path');req.pop('kind');req.pop('version');req.pop('budget_attempts')
 enqueue('075_v1_wall_metadata_retest_'+method,**req,weights_sha256=sha(Path(req['weights'])/'weights.npz'),reason='Verify actual-mode metadata repair and immediate failure decision logging; old physics failures retained, no task or safety relaxation.')
print('TWO_WALL_RETESTS_QUEUED')
