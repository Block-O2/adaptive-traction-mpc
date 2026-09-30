import unittest
from types import SimpleNamespace
import research_adapter
from research_activation import install

class ActivationTests(unittest.TestCase):
 def tearDown(self):research_adapter.MAIN_RESEARCH_PLANNER=None
 def test_rejected_activation_does_not_commit_continuation(self):
  committed=[]
  planner=SimpleNamespace(research_pending_commit={'descriptor':{'parameters':[.12,.5]},'request_id':11},research_spec={},note_research_actual_activation=committed.append)
  research_adapter.MAIN_RESEARCH_PLANNER=planner
  def on_task_activation(receipt):raise RuntimeError('authority rejected')
  def original(runtime):runtime.pop('actual_activation_hook')({'mode':'TRACK'})
  module=SimpleNamespace(_execute_interval=original);install(module)
  with self.assertRaises(RuntimeError):module._execute_interval({'actual_activation_hook':on_task_activation,'plan_to_activate':SimpleNamespace(request_id=11)})
  self.assertEqual(committed,[])
 def test_only_successful_authority_receipt_commits_once(self):
  events=[];descriptor={'parameters':[.12,.5]}
  planner=SimpleNamespace(research_pending_commit={'descriptor':descriptor,'request_id':11},research_spec={},note_research_actual_activation=lambda d:events.append(('commit',d)))
  research_adapter.MAIN_RESEARCH_PLANNER=planner
  def on_task_activation(receipt):events.append(('authority',receipt['mode']))
  def original(runtime):
   hook=runtime.pop('actual_activation_hook',None)
   if hook:hook({'mode':'TRACK'})
  module=SimpleNamespace(_execute_interval=original);install(module)
  runtime={'actual_activation_hook':on_task_activation,'plan_to_activate':SimpleNamespace(request_id=11)};module._execute_interval(runtime);module._execute_interval(runtime)
  self.assertEqual(events,[('authority','TRACK'),('commit',descriptor)])
  self.assertIsNone(planner.research_pending_commit)
  self.assertEqual(planner.research_spec['continuation_committed_at_actual_request_id'],11)
 def test_cancelled_request_cannot_commit_on_another_receipt(self):
  committed=[]
  planner=SimpleNamespace(research_pending_commit={'descriptor':{'parameters':[.12,.5]},'request_id':11},research_spec={},note_research_actual_activation=committed.append)
  research_adapter.MAIN_RESEARCH_PLANNER=planner
  def on_task_activation(receipt):pass
  def original(runtime):runtime.pop('actual_activation_hook')({'mode':'TRACK'})
  module=SimpleNamespace(_execute_interval=original);install(module)
  module._execute_interval({'actual_activation_hook':on_task_activation,'plan_to_activate':SimpleNamespace(request_id=12)})
  self.assertEqual(committed,[]);self.assertIsNone(planner.research_pending_commit)

if __name__=='__main__':unittest.main()
