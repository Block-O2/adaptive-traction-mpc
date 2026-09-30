"""Logging repair regression and read-only recovery of the actual rep1 state."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
import online_pilot as p

class LoggingRecovery(unittest.TestCase):
 def test_native_array_and_scalar_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'boundary.json'
   p.save(path,{'state':np.array([1.,2.]),'nested':{'sequence':np.int64(3),'cost':np.float64(4.)}})
   self.assertEqual(json.loads(path.read_text()),{'state':[1.,2.],'nested':{'sequence':3,'cost':4.}})
 def test_actual_rep1_checkpoint_and_pending_model(self):
  directory=p.RAW/'pilot_sessions/scratch_v1'
  rows=json.loads((directory/'per_repetition.json').read_text());self.assertEqual(len(rows),1)
  cp=rows[-1]['end_checkpoint'];prov=p.sha(directory/'session_provenance.json')
  context,restored=p.load_checkpoint(Path(cp['absolute_path']),cp['sha256'],prov)
  self.assertEqual(len(restored),1);self.assertEqual(context['repetition_index'],1)
  self.assertFalse(context['runtime']['wall_session'].active)
  self.assertIsNone(context['runtime']['plan_lifecycle']._outstanding)
  self.assertTrue(np.all(np.isfinite(context['runtime']['plant'].data.qpos)))
  updates=json.loads((directory/'training_updates.json').read_text())
  prepared=[u for u in updates if u.get('after_repetition')==1 and u.get('path')][-1]
  self.assertEqual(p.sha(Path(prepared['path'])),prepared['sha256'])
  with self.assertRaisesRegex(RuntimeError,'hash mismatch'):
   p.load_checkpoint(Path(cp['absolute_path']),'0'*64,prov)

if __name__=='__main__':unittest.main()
