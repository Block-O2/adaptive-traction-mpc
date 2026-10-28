"""Recovery-aware precondition wrapper; the sealed v1 installer is unchanged."""
from pathlib import Path
import json
import runpy
import sys

P = Path(__file__).resolve().parents[1]
if sys.argv[1] == 'bind':
    c = json.loads((P / 'experiments' / (sys.argv[2] + '.json')).read_text())
    assert c['condition']['name'] == c['group'], 'CONDITION_AND_GROUP_NAMESPACE_MISMATCH'
if sys.argv[1] == 'install':
    end = json.loads((P / 'owned/HOLDSS03_SUPERVISOR_END.json').read_text())
    assert end['state'] == 'STOP' and not end['survivors'], 'RECOVERED_SS_STILL_ACTIVE'
    for old in end['known_owned'].values():
        try:
            s = (Path('/proc') / str(old['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
            assert int(s[19]) != old['start_ticks'] or s[0] == 'Z', 'RECOVERED_SS_OWNED_LIVE'
        except FileNotFoundError:
            pass
    for f in (P / 'audit').glob('HOLDSS03*_ERROR.json'):
        assert 'TRUE_NATIVE_SAFETY_CONTRACT_FAILURE' not in str(json.loads(f.read_text()).get('error')), 'UNRESOLVED_RECOVERED_SS_HARD_SAFETY_FAILURE'
runpy.run_path(str(P / 'source/v7_factorial_install_and_bind_v2.py'), run_name='__main__')
