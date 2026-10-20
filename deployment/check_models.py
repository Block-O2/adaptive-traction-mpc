"""Hash all scoped assets and compile original robot models without stepping."""
import argparse
import json
from pathlib import Path
from reproducibility import REPO, check_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    manifest = json.loads((REPO / 'deployment/model_manifest.json').read_text())
    errors = check_rows(REPO, manifest['files'], 'MODEL_IDENTITY')
    compiled = []
    if not errors:
        import mujoco
        def forbidden(*a, **kw):
            raise RuntimeError('MODEL_CHECK_FORBIDS_PHYSICS_STEPS')
        for name in ('mj_step', 'mj_step1', 'mj_step2', 'mj_forward', 'mj_inverse'):
            setattr(mujoco, name, forbidden)
        for relative in manifest['compile_models']:
            try:
                model = mujoco.MjModel.from_xml_path(str(REPO / relative))
                compiled.append(dict(path=relative, status='PASS', nq=model.nq, nv=model.nv, nu=model.nu))
            except Exception as exc:
                errors.append('MODEL_COMPILE:' + relative + ':' + str(exc))
    report = dict(status='FAIL' if errors else 'PASS', scope=manifest['scope'],
                  identity_files=len(manifest['files']), compiled=compiled, errors=errors,
                  physics_steps=0, dynamic_physics='NOT_RUN', training='NOT_RUN')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
