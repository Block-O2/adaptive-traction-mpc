"""Control only this study's idle stage coordinator; physics is unaffected."""
from task_bootstrap import *
if sys.argv[1]=='stop':
 state=json.loads((STUDY/'PIPELINE_STATE.json').read_text()) if (STUDY/'PIPELINE_STATE.json').exists() else {'phase':'WAIT_DATA'}
 assert state['phase']=='WAIT_DATA','DO_NOT_STOP_ACTIVE_FIT'
 save(STUDY/'STOP_CONTROLLER',dict(unix=time.time(),reason='reload WAIT_DATA prerequisite to include queued zero-regression; prevents a fit/physics dispatch race'))
elif sys.argv[1]=='clear':
 path=STUDY/'STOP_CONTROLLER'
 if path.exists():path.unlink()
 print('CONTROLLER_RELOAD_READY')
