"""Phase 3 choreography: animate the arm, HAND OFF the record by the EDGE, and FLIP.

The record is held RIGIDLY by the claws at its RIM: a fixed offset `M_local` places
the disc in the gripper's frame so its edge sits in the gap between the two claws and
the disc extends along the reach axis. While held, record_world = M_local * grasp.

The flip is a 180-degree ROLL of the wrist (joint J4, about the reach axis): the claw
turns like a key, rolling the disc about its own radius — it flips side-to-side, and
its CENTER stays on the roll axis, so placement stays exact. A separate pitch wrist
(J3 = -(shoulder+elbow)) keeps the gripper level during carries.

Arm poses are solved to put the RECORD CENTER on each target; the roll is animated on
its own track. Run `python src/choreograph.py --measure` for solved poses + error.
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
ROLL_PATH, ROLL_ATTR = JOINT_INFO["roll"]

CRATE_TGT = Gf.Vec3d(-0.42, 0.055, -0.02)       # record center in the crate
PLATTER_TGT = Gf.Vec3d(0.0, 0.066, 0.0)         # record center on the platter
LIFT = Gf.Vec3d(0, 0.17, 0)
GRIP_RADIUS = 0.13                              # claws grab the rim this far from center

POSE_DEFS = {
    "OVER_CRATE":   CRATE_TGT + LIFT,
    "AT_CRATE":     CRATE_TGT,
    "OVER_PLATTER": PLATTER_TGT + LIFT,
    "AT_PLATTER":   PLATTER_TGT,
}

# (time, pose) — the arm never changes pose for the flip; only the roll joint moves.
KEYS = [
    (1,   "OVER_PLATTER"), (22, "OVER_CRATE"),
    (40,  "AT_CRATE"),          # PICK1
    (58,  "OVER_CRATE"), (92, "OVER_PLATTER"),
    (112, "AT_PLATTER"),        # PLACE1 (side A)
    (132, "OVER_PLATTER"),
    (190, "OVER_PLATTER"),
    (208, "AT_PLATTER"),        # PICK2
    (224, "OVER_PLATTER"),      # raise; the roll (flip) happens 224->250
    (250, "OVER_PLATTER"),
    (268, "AT_PLATTER"),        # PLACE2 (side B)
    (288, "OVER_PLATTER"), (312, "OVER_PLATTER"),
]
PICK1, PLACE1, PICK2, PLACE2 = 40, 112, 208, 268
FLIP_START, FLIP_END = 224, 250


def set_pose(stage, pose, time=Usd.TimeCode.Default()):
    for jname, ang in pose.items():
        path, attr = JOINT_INFO[jname]
        stage.GetPrimAtPath(path).GetAttribute(attr).Set(float(ang), time)


def grasp_matrix(stage) -> Gf.Matrix4d:
    return UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath(GRASP))


def calibrate(stage) -> Gf.Matrix4d:
    """Fix the record in the gripper frame: rim at the grasp point, disc extending
    along the gripper's reach (+Z), lying flat. Returns M_local."""
    set_pose(stage, dict(yaw=16, shoulder=5, elbow=45, wrist=-50))
    G = grasp_matrix(stage)
    reach = G.TransformDir(Gf.Vec3d(0, 0, 1))            # gripper forward, in world
    reach = Gf.Vec3d(reach[0], 0, reach[2]).GetNormalized()
    center = G.ExtractTranslation() + GRIP_RADIUS * reach
    return Gf.Matrix4d().SetTranslate(center) * G.GetInverse()   # flat disc at center


def record_center(stage, m_local) -> Gf.Vec3d:
    return (m_local * grasp_matrix(stage)).ExtractTranslation()


def solve_pose(stage, m_local, target) -> dict:
    """Search yaw/shoulder/elbow so the RECORD CENTER hits target (wrist levels it)."""
    yaw0 = math.degrees(math.atan2(target[0] - ARM_BASE[0], target[2] - ARM_BASE[2]))

    def err(yaw, sh, el):
        pose = dict(yaw=yaw, shoulder=sh, elbow=el, wrist=-(sh + el))
        set_pose(stage, pose)
        return (record_center(stage, m_local) - target).GetLength(), pose

    best = None
    for yaw in [yaw0 + i * 4 for i in range(-3, 4)]:
        for sh in range(-15, 76, 4):
            for el in range(0, 101, 4):
                e, pose = err(yaw, sh, el)
                if best is None or e < best[0]:
                    best = (e, pose, yaw, sh, el)
    _, _, by, bsh, bel = best
    for yaw in [by + i for i in range(-3, 4)]:
        for sh in [bsh + i * 0.5 for i in range(-5, 6)]:
            for el in [bel + i * 0.5 for i in range(-5, 6)]:
                e, pose = err(yaw, sh, el)
                if e < best[0]:
                    best = (e, pose, yaw, sh, el)
    return best[1]


def compute(stage):
    m_local = calibrate(stage)
    return m_local, {n: solve_pose(stage, m_local, t) for n, t in POSE_DEFS.items()}


def _rotate_op(stage, prim_path, axis):
    prim = stage.GetPrimAtPath(prim_path)
    attr = prim.GetAttribute(spec.joint_attr_name(axis))
    if not attr:
        getattr(UsdGeom.Xformable(prim), f"AddRotate{axis}Op")()
        attr = prim.GetAttribute(spec.joint_attr_name(axis))
    return attr


def author():
    solver = Usd.Stage.Open(STAGE)
    m_local, poses = compute(solver)

    stage = Usd.Stage.Open(STAGE)
    for t, key in KEYS:
        set_pose(stage, poses[key], time=Usd.TimeCode(t))

    # the flip: roll the wrist 180 (and back to 0 once the record is released)
    roll = stage.GetPrimAtPath(ROLL_PATH).GetAttribute(ROLL_ATTR)
    for t, v in [(1, 0), (FLIP_START, 0), (FLIP_END, 180), (PLACE2, 180), (288, 0)]:
        roll.Set(float(v), Usd.TimeCode(t))

    spin = _rotate_op(stage, PLATTER, "Y")
    spin.Set(0.0, Usd.TimeCode(1)); spin.Set(360.0 * 8, Usd.TimeCode(312))

    swing = _rotate_op(stage, TONEARM, "Y")
    for t, v in [(1, 0), (PLACE1 + 6, 0), (PLACE1 + 24, -28),
                 (PICK2 - 14, -28), (PICK2 - 4, 0),
                 (PLACE2 + 6, 0), (PLACE2 + 24, -28), (312, -28)]:
        swing.Set(float(v), Usd.TimeCode(t))

    # bake: crate -> gripper(A) -> platter(A) -> gripper(flip) -> platter(B)
    flip180 = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 180))
    rec_attr = stage.GetPrimAtPath(RECORD).GetAttribute("xformOp:transform")
    for f in range(int(stage.GetStartTimeCode()), int(stage.GetEndTimeCode()) + 1):
        cache = UsdGeom.XformCache(Usd.TimeCode(f))
        if f < PICK1:
            m = Gf.Matrix4d().SetTranslate(CRATE_TGT)
        elif f <= PLACE1 or (PICK2 <= f <= PLACE2):             # rigidly held
            m = m_local * cache.GetLocalToWorldTransform(stage.GetPrimAtPath(GRASP))
        else:                                                   # resting on platter
            pm = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(PLATTER))
            base = Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, 0.016, 0)) * pm
            m = (flip180 * base) if f > PLACE2 else base         # side B stays flipped
        rec_attr.Set(m, Usd.TimeCode(f))

    stage.GetRootLayer().Save()
    print("authored choreography ->", STAGE)


def measure():
    stage = Usd.Stage.Open(STAGE)
    m_local, poses = compute(stage)
    for name, tgt in POSE_DEFS.items():
        set_pose(stage, poses[name])
        c = record_center(stage, m_local)
        p = poses[name]
        print(f"  {name:14s} err={(c - tgt).GetLength()*1000:5.1f}mm  "
              f"yaw={p['yaw']:+.1f} sh={p['shoulder']:+.1f} el={p['elbow']:+.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", action="store_true")
    if ap.parse_args().measure:
        measure()
    else:
        author()


if __name__ == "__main__":
    main()
