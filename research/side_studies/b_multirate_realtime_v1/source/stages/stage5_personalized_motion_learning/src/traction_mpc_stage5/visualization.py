"""Simple engineering schematics for the provisional Stage-5 geometry."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

_CACHE_ROOT = Path(tempfile.gettempdir()) / "adaptive_traction_mpc_stage5_cache"
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
import numpy as np

from .geometry import STAGE5_GEOMETRY, Stage5Geometry
from .human import STAGE5_HUMAN, Stage5HumanParameters


def render_top_view(
    path: Path,
    *,
    geometry: Stage5Geometry = STAGE5_GEOMETRY,
    human: Stage5HumanParameters = STAGE5_HUMAN,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    hip = geometry.world_from_human.translation[:2]
    knee = hip + np.array([human.thigh_length_m, 0.0])
    ankle = knee + np.array([human.shank_length_m, 0.0])
    cuff = knee + np.array([human.sleeve_center_m, 0.0])
    base = geometry.world_from_base.translation[:2]

    fig, ax = plt.subplots(figsize=(10.5, 5.8), constrained_layout=True)
    ax.set_facecolor("#f6f2ea")
    ax.plot([hip[0], knee[0]], [hip[1], knee[1]], lw=34, color="#315f9b", solid_capstyle="round")
    ax.plot([knee[0], ankle[0]], [knee[1], ankle[1]], lw=23, color="#d8792d", solid_capstyle="round")
    ax.add_patch(Circle(knee, 0.035, color="#20252a", zorder=5))
    ax.plot([cuff[0] - 0.04, cuff[0] + 0.04], [0.0, 0.0], lw=13, color="#8636a7", solid_capstyle="round", zorder=6)
    ax.add_patch(Rectangle((base[0] - 0.09, base[1] - 0.08), 0.18, 0.16, color="#394047"))
    elbow_hint = np.array([base[0] + 0.22, base[1] + 0.18])
    ax.plot([base[0], elbow_hint[0], cuff[0],], [base[1], elbow_hint[1], cuff[1]], lw=7, color="#66717a", marker="o")
    ax.axvline(base[0], color="#71808c", ls="--", lw=1.4)
    ax.annotate("robot base\nupper-middle shank alignment", base + [-0.02, -0.13], ha="center")
    ax.annotate("thigh (larger proximal)", (0.20, 0.075), ha="center", color="#244a7c")
    ax.annotate("knee", knee + [0.0, 0.075], ha="center")
    ax.annotate("shank (smaller distal)", knee + [0.19, 0.065], ha="center", color="#a65318")
    ax.annotate("cuff at 72% shank\n(mid-lower, not ankle)", cuff + [0.0, -0.13], ha="center", color="#67277f")
    ax.annotate("ankle", ankle + [0.0, 0.06], ha="center")
    ax.set_title("Stage-5 provisional laboratory arrangement — top view")
    ax.set_xlabel("W +X: leg longitudinal [m]")
    ax.set_ylabel("W +Y: lateral [m]")
    ax.set_aspect("equal")
    ax.set_xlim(-0.13, 1.02)
    ax.set_ylim(-0.82, 0.22)
    ax.grid(alpha=0.18)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def render_cuff_closeup(
    path: Path, *, geometry: Stage5Geometry = STAGE5_GEOMETRY
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    length = geometry.cuff_bar_length_m
    adapter = float(np.linalg.norm(geometry.end_effector_from_cuff.translation))
    fig, ax = plt.subplots(figsize=(7.2, 6.2), constrained_layout=True)
    ax.set_facecolor("#f7f8fa")
    ax.add_patch(Rectangle((-0.045, -0.025), 0.09, 0.035, color="#4d5964"))
    ax.plot([0.0, 0.0], [0.0, adapter], lw=12, color="#24a0a8", solid_capstyle="round")
    ax.plot([-length / 2, length / 2], [adapter, adapter], lw=17, color="#ee9b23", solid_capstyle="round")
    ax.plot([-0.10, 0.10], [adapter, adapter], lw=34, color="#d8792d", alpha=0.22, solid_capstyle="round")
    ax.scatter([0.0], [adapter], s=70, color="#7a238f", zorder=5)
    ax.annotate("robot terminal E", (0.0, -0.035), ha="center")
    ax.annotate(f"adapter/stem  {adapter * 1000:.0f} mm\nE +Y", (0.022, adapter / 2), va="center")
    ax.annotate(f"cuff bar  {length * 1000:.0f} mm\nC +X / shank axis", (0.0, adapter + 0.038), ha="center")
    ax.annotate("C origin", (0.008, adapter - 0.018), ha="left", color="#67277f")
    ax.text(0.0, adapter + 0.078, "bar axis perpendicular to terminal/stem axis", ha="center", weight="bold")
    ax.set_title("Stage-5 end-effector / cuff — inverted-T close-up")
    ax.set_xlabel("local cuff/shank direction [m]")
    ax.set_ylabel("local terminal/stem direction [m]")
    ax.set_aspect("equal")
    ax.set_xlim(-0.15, 0.15)
    ax.set_ylim(-0.07, 0.25)
    ax.grid(alpha=0.18)
    fig.savefig(path, dpi=170)
    plt.close(fig)
