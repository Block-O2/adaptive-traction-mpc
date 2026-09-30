"""Research plan-memory commit at unchanged authoritative TRACK receipt.

Wrap the existing execution call only to observe its successful activation hook.
No plant state, force, controller math or safety result becomes a learner input.
"""
import research_adapter

def install(runtime_module):
 original=runtime_module._execute_interval
 if getattr(original,'research_activation_observer',False):return
 def execute(runtime,*args,**kwargs):
  hook=runtime.get('actual_activation_hook')
  planner=research_adapter.MAIN_RESEARCH_PLANNER
  if hook is not None and getattr(hook,'__name__','')=='on_task_activation' and planner is not None:
   pending=getattr(planner,'research_pending_commit',None)
   request=runtime.get('plan_to_activate')
   request_id=getattr(request,'request_id',None)
   if pending is not None and pending['request_id']!=request_id:
    planner.research_pending_commit=None # cancelled/rejected request cannot bind a later receipt
   elif pending is not None:
    descriptor=pending['descriptor']
    def on_research_activation(receipt):
     hook(receipt) # original authority and fallback checks must succeed first
     planner.note_research_actual_activation(descriptor)
     planner.research_spec['continuation_committed_at_actual_request_id']=request_id
     planner.research_pending_commit=None
    runtime['actual_activation_hook']=on_research_activation
  return original(runtime,*args,**kwargs)
 execute.research_activation_observer=True
 runtime_module._execute_interval=execute
