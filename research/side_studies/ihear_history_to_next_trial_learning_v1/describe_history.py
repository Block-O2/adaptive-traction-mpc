"""Additional descriptive statistics from causal history only; not policy inputs."""
from pathlib import Path
import json,hashlib
import numpy as np
P=Path(__file__).resolve().parent
def main():
    out=[]
    for f in sorted((P/'learning').glob('*_T1_RAW_HISTORY.json')):
        raw=json.loads(f.read_text());rows=raw['rows'];t=np.array([r['physical_s'] for r in rows]);dt=np.r_[np.diff(t),0.]
        ph=np.array([r['phase'] for r in rows]);force=np.linalg.norm([r['force_world_N'] for r in rows],axis=1);moment=np.linalg.norm([r['moment_world_Nm'] for r in rows],axis=1)
        q=np.array([r['estimated_q_dq'] for r in rows]);ref=np.array([r['reference_q_dq'] for r in rows]);stats={}
        for phase in ['OUTBOUND','HOLD','RETURN']:
            sel=ph==phase;stats[phase]={}
            for name,x in [('force_N',force),('moment_Nm',moment)]:
                threshold=float(np.quantile(x[sel],.9));mask=sel&(x>=threshold);running=0.;longest=0.
                for yes,d in zip(mask,dt):
                    running=running+d if yes else 0.;longest=max(longest,running)
                peak=int(np.argmax(np.where(sel,x,-np.inf)))
                stats[phase][name]=dict(peak=float(x[peak]),peak_task_s=float(t[peak]-t[0]),p90_threshold=threshold,
                    duration_at_or_above_p90_s=float(dt[mask].sum()),longest_contiguous_at_or_above_p90_s=float(longest))
            stats[phase]['estimated_start_end_deg']=[np.rad2deg(q[sel,:2][i]).tolist() for i in [0,-1]]
            stats[phase]['tracking_extrema_deg']=[np.rad2deg(fn(q[sel,:2]-ref[sel,:2],axis=0)).tolist() for fn in [np.min,np.max]]
        receipts=raw['applied_receipts'];out.append(dict(trial=raw['metadata']['trial_id'],patient=raw['metadata']['patient_id'],phases=stats,
            source_age_min_max_s=[min(r['source_age_s'] for r in rows),max(r['source_age_s'] for r in rows)],
            commanded_receipts=len(receipts),positive_native_receipts=sum(r.get('applied',False) and r.get('native_steps',0)>0 for r in receipts),
            commissioning_belief=raw['metadata']['commissioned_belief'],read_native_truth=False,used_for_action_selection=False,
            source_sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    (P/'derived/HISTORY_DESCRIPTIVE_AUDIT.json').write_text(json.dumps(dict(rows=out,scope='descriptive causal-history audit; p90 windows are not safety thresholds or optimization targets'),indent=2,ensure_ascii=False)+'\n')
    print('HISTORY_DESCRIBED',len(out),flush=True)
if __name__=='__main__':main()
