"""
Run proposed (Adaptive MPC) on MuJoCo, record GIF.
Usage: python run_proposed.py [--offset 30] [--target 90]
"""
import argparse, sys, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'algorithms'))

import mujoco
from elastic_rod_env import ElasticRodMuJoCo, S_CONTACT
from rod_traction_proposed import ProposedMPC

try:
    from PIL import Image
except ImportError:
    raise ImportError("pip install Pillow")

K_R = 100.0


def run(offset_deg, target_deg):
    theta_target = np.radians(target_deg)
    np.random.seed(42)

    env  = ElasticRodMuJoCo()
    ctrl = ProposedMPC(phi_offset_deg=offset_deg)

    cam           = mujoco.MjvCamera()
    cam.azimuth   = 90
    cam.elevation = -25
    cam.distance  = 1.8
    cam.lookat[:] = [-0.2, 0.0, 0.1]

    opt      = mujoco.MjvOption()
    renderer = mujoco.Renderer(env.model, height=400, width=640)

    frames = []
    dt     = 1 / 50
    step   = 0
    done   = False
    max_radial_force = 0.0
    max_delta_r      = 0.0

    print(f"[Proposed MPC] offset={offset_deg}° target={target_deg}°")

    while not done:
        p_m    = env.observe_pos()
        F      = ctrl.compute(p_m)
        th, dr = env.step(F)
        step  += 1

        radial_force = abs(K_R * dr)
        max_radial_force = max(max_radial_force, radial_force)
        max_delta_r      = max(max_delta_r, abs(dr))

        if step % 5 == 0:
            F_mag = np.linalg.norm(F)
            phi   = np.degrees(np.arctan2(F[1], F[0]))
            mode  = ctrl.mode_log[-1] if ctrl.mode_log else '?'
            print(f"  t={step*dt:.2f}s  θ={np.degrees(th):.1f}°"
                  f"  δr={dr*1000:.1f}mm  F={F_mag:.1f}N"
                  f"  φ={phi:.0f}°  [{mode}]")

        renderer.update_scene(env.data, camera=cam, scene_option=opt)
        frame = renderer.render()
        frames.append(Image.fromarray(frame))

        if th >= theta_target - 0.01:
            print(f"  ✓ Reached {np.degrees(th):.1f}° in {step*dt:.2f}s")
            done = True
        elif step >= int(15 * 50):
            print(f"  ✗ Timeout: final={np.degrees(th):.1f}°")
            done = True

    for _ in range(20):
        frames.append(frames[-1])

    out = HERE / 'proposed.gif'
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=400, loop=0)
    print(f"GIF → {out}")

    print(f"\n── Proposed MPC summary ──")
    print(f"  Time             : {step*dt:.2f} s")
    print(f"  Final angle      : {np.degrees(th):.1f} deg")
    print(f"  Max radial force : {max_radial_force:.2f} N  (δr={max_delta_r*1000:.1f} mm)")
    print(f"  Max |F|          : {max(ctrl.F_mag_log):.1f} N")
    modes = ctrl.mode_log
    print(f"  Modes            : explore={modes.count('explore')}  mpc={modes.count('mpc')}")
    if ctrl.conf_geo_log:
        print(f"  Conf geo (final) : {ctrl.conf_geo_log[-1]:.3f}")
    if ctrl.conf_dyn_log:
        print(f"  Conf dyn (final) : {ctrl.conf_dyn_log[-1]:.3f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--offset', type=float, default=30.0)
    p.add_argument('--target', type=float, default=90.0)
    args = p.parse_args()
    run(args.offset, args.target)

if __name__ == '__main__':
    main()