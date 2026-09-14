from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np
import pytest

from traction_mpc_stage5.config import STAGE5_CONFIG
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.plant import build_stage5_model_xml


def test_explicit_provisional_frame_chain_and_placement() -> None:
    assert STAGE5_CONFIG["provisional_not_measured"] is True
    np.testing.assert_allclose(STAGE5_GEOMETRY.world_from_base.translation, [0.60, -0.62, 0.04])
    np.testing.assert_allclose(STAGE5_GEOMETRY.world_from_human.translation, [0.0, 0.0, 0.062])
    np.testing.assert_allclose(STAGE5_GEOMETRY.end_effector_from_cuff.translation, [0.0, 0.14, 0.0])
    np.testing.assert_allclose(
        STAGE5_GEOMETRY.end_effector_from_cuff.rotation,
        [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]],
        atol=1.0e-12,
    )
    assert STAGE5_HUMAN.cuff_fraction_of_shank == pytest.approx(0.72)
    assert STAGE5_HUMAN.sleeve_center_m == pytest.approx(0.2885472)
    assert STAGE5_GEOMETRY.base_alignment_fraction_of_shank() == pytest.approx(
        STAGE5_CONFIG["geometry"]["base_alignment_fraction_of_shank_from_knee_neutral"],
        abs=1.0e-12,
    )


def test_inverted_t_bar_is_perpendicular_to_terminal_stem() -> None:
    stem_in_cuff = (
        STAGE5_GEOMETRY.end_effector_from_cuff.rotation.T
        @ STAGE5_GEOMETRY.terminal_stem_axis_in_end_effector
    )
    assert float(STAGE5_GEOMETRY.cuff_bar_axis_in_cuff @ stem_in_cuff) == pytest.approx(0.0)
    assert np.linalg.norm(STAGE5_GEOMETRY.end_effector_from_cuff.translation) == pytest.approx(0.14)


def test_stage5_xml_has_new_base_human_cuff_and_visual_bar_without_changing_donor() -> None:
    root = ET.fromstring(build_stage5_model_xml())
    base = root.find("./worldbody/body[@name='base']")
    hip = root.find("./worldbody/body[@name='hip']")
    sleeve = root.find("./worldbody/body[@name='hip']/body[@name='shank']/site[@name='sleeve_attach_site']")
    bar = root.find("./worldbody/body[@name='base']//geom[@name='stage5_cuff_bar_geom']")
    assert base is not None and hip is not None and sleeve is not None and bar is not None
    np.testing.assert_allclose(np.fromstring(base.get("pos"), sep=" "), [0.60, -0.62, 0.04])
    np.testing.assert_allclose(np.fromstring(hip.get("pos"), sep=" "), [0.0, 0.0, 0.062])
    assert float(np.fromstring(sleeve.get("pos"), sep=" ")[0]) == pytest.approx(0.2885472)
    endpoints = np.fromstring(bar.get("fromto"), sep=" ").reshape(2, 3)
    bar_vector = endpoints[1] - endpoints[0]
    assert np.linalg.norm(bar_vector) == pytest.approx(0.08)
    assert bar.get("contype") == "0" and bar.get("conaffinity") == "0"
