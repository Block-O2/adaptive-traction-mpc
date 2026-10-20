"""Static, standard-library-only checks for the GitHub research source baseline."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', help='Required exact deployment SHA, checked against local HEAD')
    parser.add_argument('--output', type=Path, help='New report path; existing reports are never overwritten')
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error('Output already exists')
    errors = []
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if args.expected_commit and head != args.expected_commit:
        errors.append(dict(check='expected_commit', actual=head, expected=args.expected_commit))
    manifest = json.loads((ROOT / 'deployment/source_manifest.json').read_text())
    syntax = 0
    asset_references = 0
    legacy_unresolved = []
    for row in manifest['files']:
        p = ROOT / row['path']
        if not p.is_file() or p.is_symlink() or p.stat().st_size != row['bytes'] or sha(p) != row['sha256']:
            errors.append(dict(check='source_identity', path=row['path']))
            continue
        if p.suffix == '.py':
            try:
                ast.parse(p.read_bytes(), filename=row['path'])
                syntax += 1
            except SyntaxError as exc:
                errors.append(dict(check='syntax', path=row['path'], error=str(exc)))
        if p.suffix == '.xml':
            tree = ET.parse(p)
            compiler = tree.getroot().find('compiler')
            for element in tree.iter():
                if 'file' not in element.attrib:
                    continue
                folder = ''
                if compiler is not None:
                    folder = compiler.get('meshdir', '') if element.tag == 'mesh' else compiler.get('texturedir', '') if element.tag == 'texture' else ''
                target = (p.parent / folder / element.attrib['file']).resolve()
                if not target.is_file():
                    issue = dict(check='xml_asset_reference', path=row['path'], file=element.attrib['file'])
                    if '/stage1/' in '/' + row['path']:
                        legacy_unresolved.append(issue)
                    else:
                        errors.append(issue)
                elif '/stage1/' not in '/' + row['path']:
                    asset_references += 1
    frozen = ROOT / 'research/side_studies/ihear_cross_patient_b_h150_v1/audit_execution/FROZEN_SOURCE_CHAIN_HASHES.json'
    canonical = ROOT / 'research/side_studies/ihear_overnight_control_learning_transition_v1'
    anchors = json.loads(frozen.read_text())['files']
    for rel, expected in anchors.items():
        if not (canonical / rel).is_file() or sha(canonical / rel) != expected:
            errors.append(dict(check='historical_frozen_source', path=rel))
    execution = json.loads((canonical / 'EXECUTION_CODE_MANIFEST_v6.json').read_text())['files']
    for rel, expected in execution.items():
        if not (canonical / rel).is_file() or sha(canonical / rel) != expected:
            errors.append(dict(check='original_execution_v6_identity', path=rel))
    package = ROOT / 'research/rl_b_cpu_handoff_v1'
    sealed = json.loads((package / 'SHA256_MANIFEST.json').read_text())['files']
    for rel, info in sealed.items():
        if not (package / rel).is_file() or sha(package / rel) != info['sha256']:
            errors.append(dict(check='rl_b_sealed_identity', path=rel))
    vendors = json.loads((package / 'audit/VENDOR_COPY_MANIFEST.json').read_text())
    report = dict(status='FAIL' if errors else 'PASS', scope='STATIC_SOURCE_AND_ASSET_IDENTITY',
                  head=head, files=len(manifest['files']), python_syntax=syntax,
                  frozen_source_anchors=len(anchors), rl_b_sealed_files=len(sealed), vendor_assets=len(vendors),
                  original_execution_v6_files=len(execution),
                  stage3_to_5_xml_asset_references=asset_references,
                  historical_stage1_asset_status='FAIL' if legacy_unresolved else 'PASS', historical_stage1_missing=legacy_unresolved,
                  errors=errors, physics='NOT_RUN', training='NOT_RUN', cloud='UNVERIFIED',
                  full_fork_replay='BLOCKED_NO_PORTABLE_PARENT_CHECKPOINT')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
