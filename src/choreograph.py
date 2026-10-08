"""Phase 2 choreography: animate the arm, and HAND OFF the record.

Opens the static `stage.usda` and authors all time-varying data:
  * the arm's joint angles (key poses -> time samples)
  * the platter spin + tonearm swing
  * the RECORD HANDOFF — the central lesson. USD's hierarchy is static (a prim can't
    change parents over time), so "the gripper is holding the record" is done by
    BAKING the record's world transform to follow the gripper for the held frames,
    then to follow the platter once placed, read each frame via UsdGeom.XformCache.

The key poses are not hand-tuned: a tiny numeric solver picks joint angles so the
gripper reaches each target, reusing forward kinematics (set joints -> read the
grasp point's world position). The motion is still keyframed; only the angles are
computed. Keeping the gripper level is enforced by wrist = -(shoulder + elbow).

Run `python src/choreograph.py --measure` to print solved poses + reach error.
"""

from __future__ import annotations

import argparse
import math
import os

from pxr import Usd, UsdGeom, Gf

import arm_spec as spec

ROOT = os.path.join(os.path.dirname(__file__), "..")
STAGE = os.path.join(ROOT, "stage.usda")

ARM = "/Cell/Arm/"
ARM_BASE = Gf.Vec3d(-0.12, 0.0, -0.42)          # must match build_stage.ARM_POS
PLATTER = "/Cell/Turntable/PlatterMount/Platter"
TONEARM = "/Cell/Turntable/TonearmBase/TonearmPivot"
RECORD = "/Cell/Records/Record0"
GRASP = ARM + spec.GRASP_SUBPATH

JOINT_INFO = {n: (ARM + sub, spec.joint_attr_name(ax)) for n, sub, ax in spec.JOINTS}

# Reach targets (world space).
CRATE_TGT = Gf.Vec3d(-0.42, 0.055, -0.02)
PLATTER_TGT = Gf.Vec3d(0.0, 0.066, 0.0)
LIFT = Gf.Vec3d(0, 0.16, 0)                      # how high "over" poses hover

# (time, pose key) — the arm's motion track.
KEYS = [
    (1,   "OVER_PLATTER"), (22, "OVER_CRATE"), (40, "AT_CRATE"), (58, "OVER_CRATE"),
    (92,  "OVER_PLATTER"), (112, "AT_PLATTER"), (132, "OVER_PLATTER"), (168, "OVER_PLATTER"),
]
GRASP_T, RELEASE_T = 40, 112


# --- forward kinematics / solving --------------------------------------------

def set_pose(stage, pose, time=Usd.TimeCode.Default()):
    for jname, ang in pose.items():
        path, attr = JOINT_INFO[jname]
        stage.GetPrimAtPath(path).GetAttribute(attr).Set(float(ang), time)


def grasp_world(stage) -> Gf.Vec3d:
    cache = UsdGeom.XformCache()
    return cache.GetLocalToWorldTransform(
        stage.GetPrimAtPath(GRASP)).ExtractTranslation()


def solve_pose(stage, target: Gf.Vec3d) -> dict:
    """Pick yaw/shoulder/elbow (wrist = -(sh+el)) so the grasp point hits target."""
    dx, dz = target[0] - ARM_BASE[0], target[2] - ARM_BASE[2]
    yaw = math.degrees(math.atan2(dx, dz))

    def err(sh, el):
        pose = dict(yaw=yaw, shoulder=sh, elbow=el, wrist=-(sh + el))
        set_pose(stage, pose)
        return (grasp_world(stage) - target).GetLength(), pose

    best = None
    # coarse grid, then refine around the best cell
    for sh in range(-10, 71, 3):
        for el in range(0, 91, 3):
            e, pose = err(sh, el)
            if best is None or e < best[0]:
                best = (e, pose, sh, el)
    _, _, bsh, bel = best
    for sh in [bsh + i * 0.5 for i in range(-6, 7)]:
        for el in [bel + i * 0.5 for i in range(-6, 7)]:
            e, pose = err(sh, el)
            if e < best[0]:
                best = (e, pose, sh, el)
    return best[1]


def compute_poses() -> dict:
    stage = Usd.Stage.Open(STAGE)                # throwaway: only for FK solving
    poses = {
        "AT_CRATE":     solve_pose(stage, CRATE_TGT),
        "OVER_CRATE":   solve_pose(stage, CRATE_TGT + LIFT),
        "AT_PLATTER":   solve_pose(stage, PLATTER_TGT),
        "OVER_PLATTER": solve_pose(stage, PLATTER_TGT + LIFT),
    }
    return poses


# --- authoring ---------------------------------------------------------------

def _rotate_op(stage, prim_path, axis):
    prim = stage.GetPrimAtPath(prim_path)
    attr = prim.GetAttribute(spec.joint_attr_name(axis))
    if not attr:
        getattr(UsdGeom.Xformable(prim), f"AddRotate{axis}Op")()
        attr = prim.GetAttribute(spec.joint_attr_name(axis))
    return attr


def author():
    poses = compute_poses()
    stage = Usd.Stage.Open(STAGE)

    # arm joints: key poses -> time samples
    for t, key in KEYS:
        set_pose(stage, poses[key], time=Usd.TimeCode(t))

    # platter spin (continuous) + tonearm swing (after placement)
    spin = _rotate_op(stage, PLATTER, "Y")
    spin.Set(0.0, Usd.TimeCode(1)); spin.Set(360.0 * 4, Usd.TimeCode(168))
    swing = _rotate_op(stage, TONEARM, "Y")
    swing.Set(0.0, Usd.TimeCode(1)); swing.Set(0.0, Usd.TimeCode(RELEASE_T + 6))
    swing.Set(-28.0, Usd.TimeCode(RELEASE_T + 24)); swing.Set(-28.0, Usd.TimeCode(168))

    # bake the record handoff: crate -> gripper -> platter
    rec_attr = stage.GetPrimAtPath(RECORD).GetAttribute("xformOp:transform")
    for f in range(int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode()) + 1):
        cache = UsdGeom.XformCache(Usd.TimeCode(f))
        if f < GRASP_T:
            m = Gf.Matrix4d().SetTranslate(CRATE_TGT)
        elif f <= RELEASE_T:
            gp = cache.GetLocalToWorldTransform(
                stage.GetPrimAtPath(GRASP)).ExtractTranslation()
            m = Gf.Matrix4d().SetTranslate(gp + Gf.Vec3d(0, -0.012, 0))
        else:
            pm = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(PLATTER))
            m = Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, 0.016, 0)) * pm
        rec_attr.Set(m, Usd.TimeCode(f))

    stage.GetRootLayer().Save()
    print("authored choreography ->", STAGE)


def measure():
    poses = compute_poses()
    stage = Usd.Stage.Open(STAGE)
    for name in ("OVER_CRATE", "AT_CRATE", "OVER_PLATTER", "AT_PLATTER"):
        set_pose(stage, poses[name])
        g = grasp_world(stage)
        tgt = {"AT_CRATE": CRATE_TGT, "OVER_CRATE": CRATE_TGT + LIFT,
               "AT_PLATTER": PLATTER_TGT, "OVER_PLATTER": PLATTER_TGT + LIFT}[name]
        p = poses[name]
        print(f"  {name:12s} grasp=({g[0]:+.3f},{g[1]:+.3f},{g[2]:+.3f}) "
              f"err={(g - tgt).GetLength()*1000:5.1f}mm  "
              f"yaw={p['yaw']:+.0f} sh={p['shoulder']:+.1f} el={p['elbow']:+.1f} wr={p['wrist']:+.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", action="store_true")
    if ap.parse_args().measure:
        measure()
    else:
        author()


if __name__ == "__main__":
    main()
