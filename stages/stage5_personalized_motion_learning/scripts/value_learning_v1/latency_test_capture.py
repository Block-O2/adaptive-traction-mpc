"""Opt-in capture preserves serialized bytes and excludes stationary proxy."""
import json
import os
from pathlib import Path
import pickle
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from latency_capture import capture_payload


def payload(index,committed):
    planner=SimpleNamespace(research_phase_index=index,research_spec={
        'proposal_descriptors':[{'id':i} for i in (0,2,3,6)],
        'committed_descriptor':{'id':6} if committed else None})
    return pickle.dumps((SimpleNamespace(planner=planner),{}))


class CaptureScopeTest(unittest.TestCase):
    def test_optout_does_not_even_unpickle(self):
        with patch.dict(os.environ,{},clear=True):capture_payload(b'not pickle',{})

    def test_moving_requires_committed_nonzero_reference_velocity(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'VALUE_LATENCY_SNAPSHOT_DIR':root}):
            args={'phase':'OUTBOUND','current_reference_state':[0.,0.,0.,0.]}
            capture_payload(payload(0,False),args)
            capture_payload(payload(1,True),args)
            self.assertFalse((Path(root)/'moving_outbound.pickle').exists())
            args['current_reference_state']=[0.,0.,.01,0.]
            capture_payload(payload(1,False),args)
            self.assertFalse((Path(root)/'moving_outbound.pickle').exists())
            actual=payload(1,True);capture_payload(actual,args)
            path=Path(root)/'moving_outbound.pickle'
            self.assertEqual(path.read_bytes(),actual)
            meta=json.loads(path.with_suffix('.json').read_text())
            self.assertEqual(meta['captured_role'],'actual_moving_committed_outbound')
            self.assertFalse(meta['reference_stationary'])
            capture_payload(payload(2,True),args)
            self.assertEqual(path.read_bytes(),actual)


if __name__=='__main__':unittest.main()
