from explore_common import *
def main():
 rows=[load(p) for p in sorted((S/'reports').glob('*_MEASURED.json'))];by={r['id']:r for r in rows};b=by.get('001_search_B');out=[]
 if b:
  for a in rows:
   if not a['id'].startswith(tuple(f'{i:03d}' for i in range(1,15))):continue
   modeldiff={}
   for key in ['model_beta','model_residual','initial_estimated_state','initial_reference']:
    try:
     aa=np.asarray(a['commissioning'][key],float);bb=np.asarray(b['commissioning'][key],float);modeldiff[key]=float(np.max(abs(aa-bb))) if aa.shape==bb.shape and aa.size else None
    except (TypeError,ValueError):modeldiff[key]=None
   c=compare(a,b)
   with np.load(S/'motion_series'/(a['id']+'.npz')) as z:entry=np.rad2deg(np.r_[z['true_q_rad'][0],z['true_dq_rad_s'][0]])
   with np.load(S/'motion_series'/(b['id']+'.npz')) as z:be=np.rad2deg(np.r_[z['true_q_rad'][0],z['true_dq_rad_s'][0]])
   out.append(dict(id=a['id'],commissioning_max_abs_differences=modeldiff,true_TASK_entry_delta_deg_deg_s=entry-be,phase_delta_J_F_N_s=c['phase_J_F_delta_N_s'],gain_percent=c['gain_percent'],acceptance_pass=c['acceptance_pass']))
 save(S/'COLD_START_ATTRIBUTION_LIMITS.json',dict(discovery=out,interpretation='Full cold initial-condition comparisons are valid descriptive host task comparisons; commissioned estimates, TASK-entry states and native timing opportunities can differ. A RETURN-only policy cannot explain OUTBOUND differences as a direct residual effect. No same-intermediate-state causal identification, artificial fit sharing or durable fork was used.'))
 print(json.dumps(clean(out),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
