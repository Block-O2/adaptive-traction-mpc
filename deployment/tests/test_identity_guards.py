"""Integrity failure tests; no synthetic scientific scoring and no physics."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reproducibility import REPO, DEFAULT_CONFIG, check_rows, digest, load_config, repository_path, verify_inputs


class IdentityGuards(unittest.TestCase):
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
