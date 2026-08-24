# UR10e vendor snapshot provenance

- Source: local MuJoCo Menagerie Git object database at
  `third_party/mujoco_menagerie/`
- Source revision: `accb6df40a9a1d1e49eff88157f6818b63a49335`
- Source subtree: `universal_robots_ur10e/`
- Upstream description: MuJoCo Menagerie UR10e model derived from the public
  ROS-Industrial UR description, as recorded in the copied `README.md`
- License: copied byte-for-byte as `universal_robots_ur10e/LICENSE`

Materialized files are limited to the runtime model and its provenance:

- `ur10e.xml`
- all 20 OBJ mesh assets referenced by `ur10e.xml`
- `LICENSE`
- `README.md`
- `CHANGELOG.md`

The upstream scene, preview PNG, and ground/sky assets were not copied because
the robot-only execution plant does not require them.

Integrity anchors:

- `ur10e.xml` SHA-256:
  `7495b8efe33e497ffe892b9279acb010671c2b4b5955f499aa2b1d320dd8c871`
- `LICENSE` SHA-256:
  `5ec71ccf66c8d03261448f2441a586765b97f2248c860a1ae19689fb1c45cee6`

The copied vendor files are not edited. The separate
`../../models/ur10e_torque.xml` execution variant preserves the vendor
worldbody, assets, geometry, inertias, joints, limits, and frames while
replacing the position-servo actuator section with explicit torque motors.
