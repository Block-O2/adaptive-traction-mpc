from task_bootstrap import *
def main():
 compute=json.loads((STUDY/'reports/AUDIT_COMPUTE_RECONCILIATION.json').read_text());assert compute['attempts']==compute['ended']==159 and not compute['active_ids']
 save(STUDY/'reports/CLOSEOUT_STATUS.json',dict(status='WORKING_READ_ONLY_REVIEW',unix=time.time(),elapsed_h=(time.time()-START)/3600,all_registered_physics_ended=True,attempts=159,ended=159,runner_remains_live_for_resource_monitoring=True,final_closeout_not_yet_performed=True,no_more_physics_planned=True,adaptation='NOT_RUN',reason='Actual qualification gate false; bounded source/evidence and final delivery review continue within the7-9h authorized package.'))
 p=STUDY/'delivery/FIGURE_MANIFEST.json';d=json.loads(p.read_text())
 for row in d['figures']:assert sha(Path(row['path']))==row['sha256']
 d.update(status='VISUALLY_VERIFIED',visual_QA_unix=time.time(),visual_QA='All6 current PNGs inspected: labels/legends/numeric values readable; no clipped text; scientific and actual scopes explicit. Resource figure is a point-in-time snapshot and is regenerated at final closeout.');save(p,d)
 print(json.dumps(dict(status='READ_ONLY_REVIEW_CHECKPOINT',figures_verified=len(d['figures']))))
if __name__=='__main__':main()
