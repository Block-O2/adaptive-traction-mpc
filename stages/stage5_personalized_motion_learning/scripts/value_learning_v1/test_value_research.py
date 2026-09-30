"""Meaningful research invariants: safety, model version, return credit, splits."""
from pathlib import Path
import tempfile, unittest
import numpy as np
from value_models import fit_ridge,fit_mlp,save_model,load_model,ValidatedModelSlot

class ModelTests(unittest.TestCase):
 def test_ridge_identifies_conditional_action_cost_and_roundtrip(self):
  rng=np.random.default_rng(3);X=rng.normal(size=(500,3));y=20+X[:,0]*X[:,2]+2*X[:,1]
  model=fit_ridge(X,y,alpha=.01,feature_names=['progress_0','beta_0','candidate_delta_0'])
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'m.npz';save_model(p,model);restored=load_model(p)
   np.testing.assert_allclose(model.predict(X),restored.predict(X),rtol=0,atol=0)
   self.assertLess(np.mean(np.abs(y-restored.predict(X))),.01)
   with self.assertRaises(FileExistsError):save_model(p,model)
 def test_boundary_model_cannot_switch_mid_repetition(self):
  X=np.array([[0.,1.],[1.,2.],[2.,3.]]);y=np.array([4.,5.,6.]);m=fit_ridge(X,y)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'m.npz';save_model(p,m);slot=ValidatedModelSlot();slot.propose(p,X)
   with self.assertRaises(RuntimeError):slot.switch(at_safe_repetition_boundary=False)
   self.assertEqual(slot.active_version,'ZERO')
   path,version=slot.switch(at_safe_repetition_boundary=True);self.assertEqual(path,str(p));self.assertEqual(len(version),64)
 def test_small_mlp_learns_nonlinear_remaining_cost(self):
  rng=np.random.default_rng(1);X=rng.uniform(-1,1,(300,3));y=100+15*X[:,0]**2+10*np.sin(X[:,1])+4*X[:,2]
  m=fit_mlp(X[:240],y[:240],validation=(X[240:],y[240:]),epochs=250,weight_decay=.0001)
  self.assertLess(np.sqrt(np.mean((m.predict(X[240:])-y[240:])**2)),2.)
  self.assertLess(m.metadata['parameter_count'],10000)
 def test_nonfinite_features_never_produce_ranked_action(self):
  X=np.array([[0.,1.],[1.,2.],[2.,3.]]);m=fit_ridge(X,np.array([4.,5.,6.]))
  with self.assertRaises(ValueError):m.predict(np.array([[np.nan,0.]]))

if __name__=='__main__':unittest.main()
