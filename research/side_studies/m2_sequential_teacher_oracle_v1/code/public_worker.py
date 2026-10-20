"""C1: existing prewarmed process-worker option, no control/source changes."""
def install(request):
 if request.get('public_version') not in ('C1','C1_THREAD','C2_THREAD'):return
 import study_common as sc
 original=sc.load_case_options
 def load():
  case,options=original();options=dict(options);options['planner_process_worker']=request.get('public_version')=='C1';return case,options
 sc.load_case_options=load
