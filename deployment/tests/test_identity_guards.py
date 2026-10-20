"""Integrity failure tests; no synthetic scientific scoring and no physics."""
import json
import os
import subprocess
import venv
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reproducibility import REPO, DEFAULT_CONFIG, check_rows, digest, load_config, repository_path, verify_inputs


class IdentityGuards(unittest.TestCase):
    def test_access_guard_activates_in_fresh_child_venv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blocked = root / 'blocked'
            blocked.mkdir()
            child = root / 'venv'
            venv.EnvBuilder(with_pip=False).create(child)
            python = child / 'bin/python'
            helper = Path(__file__).with_name('install_access_guard.py')
            subprocess.run([str(python), str(helper)], check=True, capture_output=True)
            env = os.environ.copy()
            roots = json.loads(env.get('IHEAR_FORBIDDEN_ROOTS', '[]')) + [str(blocked)]
            env.update(IHEAR_FORBIDDEN_ROOTS=json.dumps(roots), IHEAR_ACCESS_GUARD_LOG=str(root / 'guard.log'))
            probe = "import os,sys;assert '_ihear_fresh_clone_guard' in sys.modules;os.scandir(sys.argv[1])"
            result = subprocess.run([str(python), '-B', '-c', probe, str(blocked)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('FRESH_CLONE_FORBIDS_LEGACY_ROOT:', result.stderr)

    def test_repository_paths_cannot_escape(self):
        with self.assertRaises(ValueError):
            repository_path('../outside')
        with self.assertRaises(ValueError):
            repository_path('/outside')

    def test_original_fixture_byte_change_is_rejected(self):
        config = load_config()
        manifest = json.loads(repository_path(config['fixture_manifest']).read_text())
        row = next(r for r in manifest['files'] if r['path'].endswith('/config_snapshot.json'))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dest = root / row['path']
            dest.parent.mkdir(parents=True)
            shutil.copyfile(repository_path(config['fixture_root']) / row['path'], dest)
            self.assertEqual(check_rows(root, [row], 'FIXTURE'), [])
            data = bytearray(dest.read_bytes())
            data[-1] ^= 1  # Same size, original fixture copy; SHA must catch this.
            dest.write_bytes(data)
            self.assertTrue(check_rows(root, [row], 'FIXTURE'))

    def test_missing_fixtures_fail_before_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            report = verify_inputs(load_config(), Path(temp))
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(len([x for x in report['errors'] if x.startswith('FIXTURE_IDENTITY:')]), 32)

    def test_configuration_cannot_select_other_experiment(self):
        config = json.loads(DEFAULT_CONFIG.read_text())
        config['ids'] = ['other']
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'config.json'
            p.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(p)


if __name__ == '__main__':
    unittest.main()
