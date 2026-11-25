"""Compare all frozen RT2 B score fields using read-only archived inputs."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rt2-evidence", type=Path, required=True)
    parser.add_argument("--baseline-native", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "research/local_studies/ihear_lab_stage1_rt2_v1"))
    import score

    score.HERE = args.rt2_evidence.resolve()
    score.BASE = args.baseline_native.resolve()
    expected = json.loads((score.HERE / "B_score.json").read_text())
    captured = {}

    def capture(_path, result):
        captured.update(json.loads(json.dumps(result, allow_nan=False,
                                              default=lambda value: value.tolist())))

    score.save = capture
    score.main()
    mismatches = sorted(key for key in expected.keys() | captured.keys()
                        if key not in expected or key not in captured
                        or expected[key] != captured[key])
    print(json.dumps({"fields": len(expected), "mismatches": mismatches,
                      "receipts": captured["receipt_n"],
                      "jf_n_s": captured["rows"]["TASK"]["jf"],
                      "matched_trace": captured["matched_trace"]}))
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())
