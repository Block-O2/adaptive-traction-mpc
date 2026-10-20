from common import *
from interface import pattern,CoordinationInterface
from schedule import *
import unittest
class ResidualContractTests(unittest.TestCase):
 def test_patterns_and_endpoints(self):
  for phase in ('OUTBOUND','RETURN'):
   for kind in ('hip','knee','reversal','catchup'):
    a=pattern(phase,kind);f=a.realize()
    for s in (0.,1.):np.testing.assert_allclose([f(s,j) for j in range(3)],0.,atol=1e-11,rtol=0)
    xs=np.linspace(0,1,501);y=f(xs)
    if kind=='hip':self.assertGreater(np.max(y),.02)
    if kind=='knee':self.assertLess(np.min(y),-.02)
    if kind=='reversal':self.assertTrue(np.max(y)>.02 and np.min(y)<-.02)
    if kind=='catchup':self.assertLess(abs(float(f(.8))),1e-12)
 def test_repeated_updates_preserve_C2(self):
  previous=pattern('OUTBOUND','hip').realize()
  for s,new_value in ((.1,-.01),(.35,.02),(.7,-.005)):
   old=tuple(float(previous(s,j)) for j in range(3));next_action=ResidualAction.scalar('OUTBOUND',s,old,new_value,min(s+.15,.9));new=next_action.realize()
   np.testing.assert_allclose([new(s,j) for j in range(3)],old,atol=1e-10,rtol=0);previous=new
  np.testing.assert_allclose([previous(1.,j) for j in range(3)],0.,atol=1e-10,rtol=0)
 def test_invalid_rejected(self):
  for args in [('HOLD',0,(0,0,0),((1,0),),1),('OUTBOUND',0,(0,0,0),((1,.1),),1),('OUTBOUND',0,(0,0,0),((.5,.1),(.4,0)),.4),('OUTBOUND',0,(0,0,0),((1,np.nan),),1),('OUTBOUND',0,(.1,0,0),((1,0),),1)]:
   with self.assertRaises(ValueError):ResidualAction(*args)
 def test_common_progress_and_envelope(self):
  for p in (np.array([.1,.3]),np.array([.8,.9]),np.array([.5,.4])):
   lo,hi=feasible_residual_envelope(p)
   for d in (lo,(lo+hi)/2,hi):
    q=p+np.array([d,-d]);self.assertTrue(np.all(q>=-1e-12) and np.all(q<=1+1e-12));self.assertAlmostEqual(float(q.mean()),float(p.mean()),places=15)
 def test_zero_exact_tape(self):
  x=CoordinationInterface();z=np.load(L/'B_TAPE.npz')
  for phase,tape in x.tapes.items():
   m=z['phase']==phase
   for i,t in enumerate(tape.t):
    sample=tape.sample(t)
    for value,raw in ((sample.q_rad,z['q'][m][i]),(sample.dq_rad_s,z['v'][m][i]),(sample.ddq_rad_s2,z['a'][m][i])):np.testing.assert_allclose(value,raw,atol=1e-10,rtol=0)
 def test_independent_return(self):
  a=pattern('OUTBOUND','hip').realize();b=pattern('RETURN','knee').realize();self.assertGreater(float(a(.3)),0);self.assertLess(float(b(.3)),0)
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(ResidualContractTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 save('UNIT_TESTS.json',dict(pass_=result.wasSuccessful(),tests_run=result.testsRun,failures=[str(x) for x in result.failures],errors=[str(x) for x in result.errors],scope='schedule API only; does not establish full physical execution readiness'))
 sys.exit(0 if result.wasSuccessful() else 1)
