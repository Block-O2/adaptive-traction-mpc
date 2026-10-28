"""Finite frozen early-activation menu; required control failures halt before later arms."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def sequence(study,config):
 required=set(config.get('required_repeat_controls',[]))
 qualified=set(config.get('required_qualified_controls',[]))
 for action in config['actions']:
  for relative,expected in config.get('frozen_reference_raw_sha256',{}).items():
   assert sha(P/relative)==expected,'FROZEN_REFERENCE_RAW_CHANGED:'+relative
  yield action
  tag=action['tag']
  if tag in required:
   ident=config['group']+'_'+tag;row=study.last_row
   assert row['id']==ident,'REGISTERED_CONTROL_RESULT_IDENTITY'
   assert row['complete'],'REGISTERED_CONTROL_INCOMPLETE:'+tag
   gate=json.loads((P/'audit'/(ident+'_HISTORICAL_IDENTITY.json')).read_text())
   assert gate['status']=='PASS','REGISTERED_CONTROL_RAW_IDENTITY:'+tag
  if tag in qualified:assert study.last_row['qualified'],'REGISTERED_CONTROL_QUALIFICATION:'+tag
