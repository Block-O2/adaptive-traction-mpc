"""Plot actual frozen continuous T3 results; no model calls or fitting."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


def main():
    started = time.monotonic()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    prefix = "V8CONTILC01_T2_H150_T3_"
    tags = ["H150", "FIXED_X3_MINUS025", "ILC_ENABLED_G025", "ILC_HISTORY_DISABLED",
            "ILC_ENABLED_G010", "FIXED_X3_PLUS025"]
    labels = ["H150", "Fixed -0.25", "Own history, gain .25", "History disabled",
              "Own history, gain .10", "Fixed +0.25"]
    rows, sources = [], {}
    for tag, label in zip(tags, labels):
        rel = "attempts/" + prefix + tag + "_RESULT.json"
        path = P / rel
        raw = path.read_bytes()
        row = json.loads(raw)
        assert row["complete"] is True and row["qualified"] is True
        sources[rel] = hashlib.sha256(raw).hexdigest()
        x = 0. if tag == "H150" else row["action"]["x"][3]
        rows.append({"label": label, "x3": x, "JF": row["JF"], "JM": row["JM"], "id": row["id"]})
    anchor = rows[0]
    colors = ["#475569", "#d97706", "#2563eb", "#7c3aed", "#059669", "#b45309"]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.3), constrained_layout=True)
    for ax, field, unit in zip(axes, ["JF", "JM"], ["N s", "N m s"]):
        ordered = sorted(rows, key=lambda row: row["x3"])
        ax.plot([row["x3"] for row in ordered], [row[field] - anchor[field] for row in ordered],
                color="#cbd5e1", linewidth=1.4, zorder=1)
        for row, color in zip(rows, colors):
            ax.scatter(row["x3"], row[field] - anchor[field], s=55, color=color, zorder=2)
        ax.axhline(0, color="#94a3b8", linewidth=.8)
        ax.set_xlabel("Registered RETURN coordinate x3")
        ax.set_ylabel("Delta " + field + " versus same-start H150 (" + unit + ")")
        ax.grid(alpha=.18)
        ax.set_xlim(-.28, .28)
    handles = [axes[0].scatter([], [], s=40, color=color, label=row["label"]) for row, color in zip(rows, colors)]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, frameon=False)
    fig.suptitle("Actual continuous T3: lower force trades against higher moment\nAll six complete and qualified; exposed condition, not new-patient validation", fontsize=11)
    outputs = {}
    for suffix in ["png", "pdf", "svg"]:
        path = P / "figures" / ("CONTINUOUS_HISTORY_TRADEOFF_V1." + suffix)
        assert not path.exists()
        fig.savefig(path, dpi=180)
        outputs[str(path.relative_to(P))] = hashlib.sha256(path.read_bytes()).hexdigest()
    plt.close(fig)
    path = P / "audit/CONTINUOUS_HISTORY_TRADEOFF_FIGURE_V1.json"
    with path.open("x") as stream:
        json.dump({"status": "PLOTTED_ACTUAL_RESULTS_NO_NEW_FIT", "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "source_result_sha256": sources, "rows": rows, "outputs": outputs,
                   "wall_s": time.monotonic() - started, "model_forward_fit_physics": 0,
                   "connecting_segments_are_not_a_fitted_model": True}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PLOTTED", "wall_s": time.monotonic() - started, "model_forward_fit_physics": 0}))


if __name__ == "__main__":
    main()
