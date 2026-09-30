"""Archive equality, provenance and local-request-join accounting guards."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from latency_evidence import analyze_artifacts,archived_json


def artifact(age,*,request_id=7,feature_start=2_000_000):
    request=dict(stage='TASK',request_id=request_id,outcome='ACTIVATED',
                 sensor_capture_ns=0,source_sample_time_s=0,
                 activation_age_ms=age,activation_ns=int(age*1e6),
                 validation_finish_ns=int((age-1)*1e6),disposition_age_ms=age+.1)
    latency=dict(candidate_count=6,feasible_count=5,decision_total_ms=3,
                 first_feature_start_ns=feature_start)
    decision=dict(candidate_count=16,timing_request_id=request_id,executed_label='selected',
                  evaluations=[dict(label='selected',schedule={'duration_s':.5},
                                    execution_screen={'research_latency':latency})])
    return dict(execution_mode='SCIENTIFIC_SIMULATION',requests=[request],
                task_decisions=[decision],future_handoff_bridges=[])


class ArchiveAccountingTest(unittest.TestCase):
    def test_original_content_hash_matches_archive_and_explicit_gzip_path(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'runtime_artifacts.json'
            content=json.dumps(artifact(10)).encode();archive=Path(str(raw)+'.gz')
            with gzip.open(archive,'wb') as stream:stream.write(content)
            value,metadata=archived_json(archive)
            self.assertEqual(value,artifact(10))
            self.assertEqual(metadata['original_content_sha256'],hashlib.sha256(content).hexdigest())
            self.assertEqual(metadata['gzip_sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertTrue(metadata['archived'])

    def test_raw_and_archive_have_same_latency_not_same_storage_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'runtime_artifacts.json';raw.write_text(json.dumps(artifact(10)))
            direct=analyze_artifacts([raw])
            with gzip.open(str(raw)+'.gz','wb') as stream:stream.write(raw.read_bytes())
            raw.unlink()
            compressed=analyze_artifacts([raw])
            self.assertEqual(direct['sample_capture_to_actual_activation_ms'],compressed['sample_capture_to_actual_activation_ms'])
            self.assertEqual(direct['source_artifacts'][0]['sha256'],compressed['source_artifacts'][0]['sha256'])

    def test_same_local_request_ids_do_not_cross_join_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for index,age in enumerate((10,20)):
                path=Path(directory)/str(index)/'runtime_artifacts.json'
                path.parent.mkdir();path.write_text(json.dumps(artifact(age)));paths.append(path)
            result=analyze_artifacts(paths)
            group=result['candidate_count_scaling']['6']
            self.assertEqual(group['joined_full_age_ms']['count'],2)
            self.assertEqual(group['joined_full_age_ms']['median'],15)
            self.assertEqual(result['exact_research_to_validation_activation_boundaries_ms']['first_feature_start_to_actual_activation_ms']['median'],13)

    def test_missing_raw_is_retained_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result=analyze_artifacts([Path(directory)/'missing.json'])
            self.assertFalse(result['source_complete'])
            self.assertEqual(len(result['input_read_failures']),1)
            self.assertEqual(result['task_request_count'],0)

    def test_snapshot_extra_io_annotation_applies_only_to_capture_run(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for index in range(2):
                path=Path(directory)/str(index)/'runtime_artifacts.json'
                path.parent.mkdir();path.write_text(json.dumps(artifact(10)));paths.append(path)
            result=analyze_artifacts(paths,capture_profile_paths=[paths[0]])
            self.assertEqual(result['snapshot_capture_extra_io_source_count'],1)
            self.assertFalse(result['source_artifacts'][1]['snapshot_capture_extra_io'])

    def test_incompatible_absolute_clocks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime_artifacts.json'
            path.write_text(json.dumps(artifact(10,feature_start=30_000_000)))
            with self.assertRaises(ValueError):analyze_artifacts([path])

    def test_unrelated_json_does_not_claim_complete_timing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runtime_artifacts.json'
            path.write_text('{"status":"PASS"}')
            result=analyze_artifacts([path])
            self.assertFalse(result['source_complete'])
            self.assertIn('missing required request evidence',result['input_read_failures'][0]['error'])


if __name__=='__main__':unittest.main()
