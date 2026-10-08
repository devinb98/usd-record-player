"""Shared description of the arm's joint chain.

Both `build_assets.py` (which authors the geometry + physics) and `choreograph.py`
(which animates the joints) import this so they agree on prim paths and axes.

Paths are given *relative to the arm root*. In the asset the root is `/Arm`; in the
assembled stage the arm is referenced at `/Cell/Arm`, so prepend the right prefix.
"""

from __future__ import annotations

# (name, subpath-under-arm-root, rotation axis)
#   wrist (X) is a pitch used to keep the gripper level; roll (Z) spins the claw
#   about the reach axis — that's what flips the record side-to-side.
JOINTS = [
    ("yaw",      "Base/Yoke",                                    "Y"),
    ("shoulder", "Base/Yoke/UpperArm",                           "X"),
    ("elbow",    "Base/Yoke/UpperArm/Forearm",                   "X"),
    ("wrist",    "Base/Yoke/UpperArm/Forearm/Gripper",           "X"),
    ("roll",     "Base/Yoke/UpperArm/Forearm/Gripper/Roll",      "Z"),
]

# A frame at the pinch point between the claws — we read its world transform to
# attach the record during the grasp handoff.
GRASP_SUBPATH = "Base/Yoke/UpperArm/Forearm/Gripper/Roll/GraspPoint"

# Link dimensions (meters), shared so geometry and reach stay consistent.
POST_HEIGHT = 0.30
UPPERARM_LEN = 0.30
FOREARM_LEN = 0.28


def joint_attr_name(axis: str) -> str:
    """The xformOp attribute a joint's angle lives on (authored by AddRotate{X,Y}Op)."""
    return f"xformOp:rotate{axis}"
