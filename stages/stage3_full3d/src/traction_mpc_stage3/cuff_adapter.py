"""Parameterized UR10e-surrogate wrist-to-cuff adapter geometry.

The dimensions below are derived only from committed MuJoCo geometry.  They
are an engineering surrogate for simulation and are not CR12 hardware
dimensions or a hardware calibration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CuffAdapterGeometry:
    wrist_collision_radius_m: float = 0.046
    wrist_collision_half_length_m: float = 0.020
    wrist_collision_center_y_in_wrist_m: float = 0.097
    attachment_site_y_in_wrist_m: float = 0.100
    cuff_outer_radius_m: float = 0.058
    shank_radius_m: float = 0.045

    @property
    def wrist_extent_toward_cuff_from_attachment_m(self) -> float:
        # attachment +Y is wrist_3_link -Y because the attachment-site frame
        # is rotated 180 degrees about X.  Include the cylinder cap radius.
        centerline_extent = self.attachment_site_y_in_wrist_m - (
            self.wrist_collision_center_y_in_wrist_m
            - self.wrist_collision_half_length_m
        )
        return centerline_extent + self.wrist_collision_radius_m

    @property
    def modeled_cuff_shell_allowance_m(self) -> float:
        return self.cuff_outer_radius_m - self.shank_radius_m

    @property
    def cuff_center_standoff_m(self) -> float:
        return (
            self.wrist_extent_toward_cuff_from_attachment_m
            + self.cuff_outer_radius_m
            + self.modeled_cuff_shell_allowance_m
        )

    @property
    def connector_length_to_cuff_surface_m(self) -> float:
        return self.cuff_center_standoff_m - self.cuff_outer_radius_m

    @property
    def connector_radius_m(self) -> float:
        return self.modeled_cuff_shell_allowance_m

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = asdict(self)
        result.update(
            {
                "wrist_extent_toward_cuff_from_attachment_m": (
                    self.wrist_extent_toward_cuff_from_attachment_m
                ),
                "modeled_cuff_shell_allowance_m": (
                    self.modeled_cuff_shell_allowance_m
                ),
                "cuff_center_standoff_m": self.cuff_center_standoff_m,
                "connector_length_to_cuff_surface_m": (
                    self.connector_length_to_cuff_surface_m
                ),
                "connector_radius_m": self.connector_radius_m,
                "translation_axis_in_attachment": "+Y",
                "rotation_attachment_from_cuff": "identity",
                "derivation": (
                    "wrist directional envelope + cuff outer radius + existing "
                    "cuff-minus-shank radial shell allowance"
                ),
                "scope": (
                    "MuJoCo Menagerie UR10e engineering surrogate only; not "
                    "actual CR12 hardware geometry or calibration"
                ),
            }
        )
        return result


CUFF_ADAPTER = CuffAdapterGeometry()

