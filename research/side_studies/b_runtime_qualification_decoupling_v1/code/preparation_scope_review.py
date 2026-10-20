"""Read-only evidence of the inspected causal preparation authority."""
from task_bootstrap import *
import ast

def main():
 root=STUDY/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1'
 specs=[(root/'online_planning.py',['@dataclass(frozen=True)','class PlanRequest:','One outstanding request','Scheduler, clearance geometry, model, belief and numeric states','if self.closed or self._outstanding is not None','self._captures[source], self.clock()','all timestamps are write-once','offline before active physical epoch']),
        (STUDY/'deps/coordination_adapter.py',['HOLD_OR_NONMOVEMENT','NATIVE_TERMINAL_OWNERSHIP','snapshot_task_call(b[','FROZEN_HUMAN_MODEL_DRIFT','raw=np.r_']),
        (root/'activation_validation.py',['def validate_activation','def validate_rolling_composite','AdaptiveMechanicsScreenV22().evaluate']),
        (STUDY/'code/async_native_worker.py',['prior_counts=','COORD.carry=prior_carry','selection is not None and age_ms>deadline','deadline=min'])]
 rows=[]
 for path,patterns in specs:
  lines=path.read_text().splitlines();matches=[dict(line=i,text=line.strip()) for i,line in enumerate(lines,1) if any(p in line for p in patterns)];assert matches
  rows.append(dict(path=str(path),sha256=sha(path),matches=matches))
 op=ast.parse(specs[0][0].read_text());request=next(x for x in op.body if isinstance(x,ast.ClassDef) and x.name=='PlanRequest');frozen=any(isinstance(x,ast.Call) and any(k.arg=='frozen' and isinstance(k.value,ast.Constant) and k.value.value is True for k in x.keywords) for x in request.decorator_list);assert frozen
 out=dict(status='INSPECTED_CAUSAL_API_SCOPE_RECORDED',rows=rows,request_dataclass_frozen=True,allowed_state_independent_scope=['Fixed candidate templates and static transforms without current/future state prediction','Offline imports/process warm-up before the physical epoch'],boundary_dependent_work_retained=['Immutable captured current deployable snapshot and ownership','Current causal observation and Q features','All original candidate certificates','Original current-model activation revalidation and source-age/expiry checks'],observed_existing_path='E5 executes the current causal snapshot/context/Q/certificates in the existing TASK worker; it does not authorize a future boundary or predict its state.',architecture_blocker='The inspected interface grants residual authority only at the current OUTBOUND/RETURN nonterminal boundary. The lifecycle permits one outstanding request. Static preparation cannot replace the remaining state-dependent certificate/admission/5ms physical feedback work.',scope_limitation='A source review of these inspected APIs, not a universal proof that no future architectural extension is possible. No new speculative request, cached future-state Q, changed control authority or third public-B scheduling repair was implemented.',physics_attempts_added=0,Q_updates=0)
 save(STUDY/'reports/PREPARATION_SCOPE_REVIEW.json',out);print(json.dumps({k:out[k] for k in ('status','request_dataclass_frozen','physics_attempts_added','Q_updates')}))
if __name__=='__main__':main()
