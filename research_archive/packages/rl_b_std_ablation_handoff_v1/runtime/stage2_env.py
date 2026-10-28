"""Task-pretrained development fine-tuning; used only after a frozen Stage2 gate."""
from pilot_env import PilotEnv
from ready_env import ReadyEnv
from common import ROOT,put
import json
class Stage2Env(PilotEnv):
 def __init__(self,*args,**kwargs):
  self.stage2_config=json.loads((ROOT/'STAGE2_FROZEN.json').read_text())
  if not self.stage2_config['gate_pass']:raise RuntimeError('STAGE2_GATE_CLOSED')
  super().__init__(*args,**kwargs)
 def _reward(self,success=False,failure=False):
  # Keep gamma=1, original progress, success evidence, terminal failure shaping.
  if success:
   from ready_env import completion_evidence
   if not completion_evidence(self.summary,self.phases):raise RuntimeError('INVALID_COMPLETION')
  if failure:self.phi=0.
  c=self.stage2_config['reward']
  parts={'progress':5.*(self.phi-self.last_phi),'completion':20. if success else -10. if failure else 0.,'force':-c['force_weight']*(self.force_integral-self.last_force)/100.,'variation':-c['variation_weight']*(self.motion_variation-self.last_variation)}
  self.last_phi=self.phi;self.last_force=self.force_integral;self.last_variation=self.motion_variation
  for k,v in parts.items():self.reward_totals[k]+=v
  if failure:
   padding=max(0.,c['failure_cost_floor']+self.reward_totals['force']+self.reward_totals['variation'])
   parts['completion']-=padding;self.reward_totals['completion']-=padding
  return sum(parts.values()),parts
 def tick(self,*args,**kwargs):
  super().tick(*args,**kwargs)
  if getattr(self,'_stage2_contract_episode',None)!=self.episode_index:
   self._stage2_contract_episode=self.episode_index
   p=self.episode_dir/'public_reward_contract.json';spec=json.loads(p.read_text());spec.update({k:self.stage2_config['reward'][k] for k in ('force_weight','variation_weight')});put(p,spec)
   put(self.episode_dir/'stage2_reward_contract.json',self.stage2_config)
