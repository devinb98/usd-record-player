"""UsdPhysics authoring helpers — the *sim-ready* layer of the robot arm.

These author the physics schema (rigid bodies, revolute joints, drives, an
articulation root) as real USD data. On macOS there's no PhysX solver, so the arm
is *played back* by animating the visual Xform chain (forward kinematics); this
schema is inert locally but is exactly what Isaac Sim / PhysX consume on an RTX box.

Articulation structure we build:
    world --fixed--> Base --J0(Y)--> Yoke --J1(X)--> UpperArm
                     --J2(X)--> Forearm --J3(X)--> Gripper
Each link is a rigid body; each joint connects two consecutive links.
"""

from __future__ import annotations

from pxr import Usd, UsdPhysics, Sdf, Gf


def make_articulation_root(prim: Usd.Prim) -> None:
    """Mark the subtree as one articulated system (reduced-coordinate solve)."""
    UsdPhysics.ArticulationRootAPI.Apply(prim)


def make_rigid_body(prim: Usd.Prim, *, mass: float = 0.5,
                    kinematic: bool = False) -> None:
    """Make a prim a dynamic rigid body with a mass and a collider.

    `kinematic=True` is used for the base: it's part of the body set but not driven
    by forces (it's pinned). Implicit gprims (cube/cylinder) get collision directly.
    """
    rb = UsdPhysics.RigidBodyAPI.Apply(prim)
    if kinematic:
        rb.CreateKinematicEnabledAttr(True)
    m = UsdPhysics.MassAPI.Apply(prim)
    m.CreateMassAttr(mass)
    UsdPhysics.CollisionAPI.Apply(prim)


def _set_bodies(joint, body0: str, body1: str) -> None:
    # body0 == "" means "the world" (an anchor for the base's fixed joint).
    if body0:
        joint.CreateBody0Rel().SetTargets([Sdf.Path(body0)])
    else:
        joint.CreateBody0Rel().SetTargets([])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(body1)])


def add_fixed_joint(stage: Usd.Stage, path: str, *, body1: str,
                    body0: str = "") -> UsdPhysics.FixedJoint:
    """Weld body1 to body0 (default: to the world) — pins the arm base down."""
    j = UsdPhysics.FixedJoint.Define(stage, path)
    _set_bodies(j, body0, body1)
    return j


def add_revolute_joint(stage: Usd.Stage, path: str, *, body0: str, body1: str,
                       axis: str, local_pos0, local_pos1=(0, 0, 0),
                       lower: float = -180.0, upper: float = 180.0,
                       stiffness: float = 2000.0, damping: float = 200.0,
                       max_force: float = 1000.0) -> UsdPhysics.RevoluteJoint:
    """A hinge between two links + an angular position drive (a PD-style motor).

    `local_pos0/1` are the joint anchor in each body's local frame (in that body's
    units). Our child link origins sit *at* the joint, so local_pos1 is (0,0,0) and
    local_pos0 is the child's offset within the parent. `axis` is 'X'/'Y'/'Z'.
    The DriveAPI(angular) target is what you'd command in simulation.
    """
    j = UsdPhysics.RevoluteJoint.Define(stage, path)
    _set_bodies(j, body0, body1)
    j.CreateAxisAttr(axis)
    j.CreateLocalPos0Attr(Gf.Vec3f(*local_pos0))
    j.CreateLocalPos1Attr(Gf.Vec3f(*local_pos1))
    j.CreateLowerLimitAttr(lower)
    j.CreateUpperLimitAttr(upper)
    drive = UsdPhysics.DriveAPI.Apply(j.GetPrim(), "angular")
    drive.CreateTypeAttr("force")
    drive.CreateStiffnessAttr(stiffness)
    drive.CreateDampingAttr(damping)
    drive.CreateMaxForceAttr(max_force)
    drive.CreateTargetPositionAttr(0.0)
    return j
