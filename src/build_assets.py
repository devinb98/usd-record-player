"""Phase 1 assets: author `assets/turntable.usda` and `assets/record.usda`.

Each file is a self-contained, *referenceable* component:
  * it has a `defaultPrim` (so a consumer knows the root to pull in), and
  * it is tagged `kind = "component"` (model hierarchy / pipeline metadata).

Design note — "pivot" Xforms:
  The platter and tonearm each get a bare Xform (`Platter`, `TonearmPivot`) that
  carries *no* transform ops of its own. The stage/choreography layer animates the
  rotation on those bare pivots. Why: `xformOpOrder` is a single attribute, and the
  strongest layer that authors it wins the whole list. Keeping the animated pivot
  free of asset-authored ops avoids a stage override clobbering an asset translate.
"""

from __future__ import annotations

import os

from pxr import Usd, UsdGeom, Gf

import usd_helpers as h
import physics as phys
import arm_spec as spec

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


def build_turntable(path: str) -> None:
    stage = Usd.Stage.CreateNew(path)
    h.configure_stage(stage)

    root = h.add_xform(stage, "/Turntable")
    h.mark_kind(root.GetPrim(), "component")
    h.set_default_prim(stage, root.GetPrim())

    # Plinth / base: a wide flat dark box sitting on the ground (bottom at y=0).
    h.add_box(stage, "/Turntable/Base", size=(0.40, 0.05, 0.34),
              translate=(0, 0.025, 0), color=(0.05, 0.05, 0.06), roughness=0.5)

    # PlatterMount carries the *height*; Platter (its child) is the bare spin pivot.
    mount = h.add_xform(stage, "/Turntable/PlatterMount")
    h.set_translate(mount, (0, 0.05, 0))
    h.add_xform(stage, "/Turntable/PlatterMount/Platter")  # <- stage animates rotateY
    h.add_disc(stage, "/Turntable/PlatterMount/Platter/PlatterDisc",
               radius=0.155, height=0.012, translate=(0, 0.006, 0),
               color=(0.08, 0.08, 0.09), roughness=0.4)

    # Tonearm: TonearmBase sets the pivot location; TonearmPivot is the bare pivot.
    tbase = h.add_xform(stage, "/Turntable/TonearmBase")
    h.set_translate(tbase, (0.135, 0.05, -0.12))
    h.add_xform(stage, "/Turntable/TonearmBase/TonearmPivot")  # <- stage swings this
    h.add_box(stage, "/Turntable/TonearmBase/TonearmPivot/Arm",
              size=(0.012, 0.012, 0.22), translate=(0, 0.03, 0.10),
              color=(0.6, 0.6, 0.62), roughness=0.3)
    h.add_box(stage, "/Turntable/TonearmBase/TonearmPivot/Head",
              size=(0.03, 0.02, 0.03), translate=(0, 0.025, 0.205),
              color=(0.15, 0.15, 0.16), roughness=0.4)

    stage.GetRootLayer().Save()
    print("wrote", path)


# Album looks for the record's variant set: (side-A label, side-B label) colors.
ALBUMS = {
    "Classic": ((0.75, 0.18, 0.12), (0.90, 0.85, 0.70)),   # red  / cream
    "Jazz":    ((0.10, 0.50, 0.50), (0.85, 0.65, 0.10)),   # teal / gold
    "Night":   ((0.35, 0.20, 0.55), (0.70, 0.72, 0.75)),   # purple / silver
}


def _set_label_color(stage, mat_path, color) -> None:
    """Override a UsdPreviewSurface's diffuseColor (used inside a variant)."""
    shader = stage.GetPrimAtPath(mat_path + "/Preview")
    shader.GetAttribute("inputs:diffuseColor").Set(Gf.Vec3f(*color))


def build_record(path: str) -> None:
    stage = Usd.Stage.CreateNew(path)
    h.configure_stage(stage)

    root = h.add_xform(stage, "/Record")
    h.mark_kind(root.GetPrim(), "component")
    h.set_default_prim(stage, root.GetPrim())

    # Vinyl: a thin black glossy disc, thick enough to separate the two faces.
    h.add_disc(stage, "/Record/Vinyl", radius=0.145, height=0.006,
               color=(0.02, 0.02, 0.02), roughness=0.15)
    # Two labels — side A on the top face (+Y), side B on the bottom (-Y) — so the
    # flip visibly swaps which face is up. Colors are set by the variant set below.
    h.add_disc(stage, "/Record/LabelA", radius=0.05, height=0.001,
               translate=(0, 0.0035, 0), color=ALBUMS["Classic"][0], roughness=0.8)
    h.add_disc(stage, "/Record/LabelB", radius=0.05, height=0.001,
               translate=(0, -0.0035, 0), color=ALBUMS["Classic"][1], roughness=0.8)
    # An off-center marker on each face so the spin reads whichever side is up.
    h.add_box(stage, "/Record/MarkerA", size=(0.012, 0.004, 0.012),
              translate=(0.085, 0.004, 0), color=(0.95, 0.9, 0.3), roughness=0.5)
    h.add_box(stage, "/Record/MarkerB", size=(0.012, 0.004, 0.012),
              translate=(0.085, -0.004, 0), color=(0.3, 0.85, 0.9), roughness=0.5)

    # --- variant set: "album" swaps the label colors --------------------------
    # A variant set is a named switch; each variant authors a different set of
    # opinions (here, the two label colors). The stage can select per-record.
    #
    # LIVRPS gotcha: add_disc already authored a *local* diffuseColor, and Local
    # beats Variant in strength ordering — so a variant opinion would be masked.
    # Clear the local color first so the variants are the only opinions.
    for mp in ("/Record/LabelA_mat", "/Record/LabelB_mat"):
        stage.GetPrimAtPath(mp + "/Preview").GetAttribute("inputs:diffuseColor").Clear()

    vset = root.GetPrim().GetVariantSets().AddVariantSet("album")
    for name, (ca, cb) in ALBUMS.items():
        vset.AddVariant(name)
        vset.SetVariantSelection(name)
        with vset.GetVariantEditContext():     # edits here land *inside* this variant
            _set_label_color(stage, "/Record/LabelA_mat", ca)
            _set_label_color(stage, "/Record/LabelB_mat", cb)
    vset.SetVariantSelection("Classic")        # default selection

    stage.GetRootLayer().Save()
    print("wrote", path)


def _joint_link(stage, path, *, translate, axis, mass):
    """A kinematic-chain link: an Xform whose origin IS the joint pivot.

    Op order is [translate, rotate]: the rotate (the joint angle, animated later by
    choreograph.py) acts about the link's local origin, then translate places that
    origin at the parent's socket. The link is also a physics rigid body.
    """
    link = UsdGeom.Xform.Define(stage, path)
    xf = UsdGeom.Xformable(link)
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))        # socket in parent frame
    getattr(xf, f"AddRotate{axis}Op")().Set(0.0)         # joint angle (xformOp:rotate{axis})
    phys.make_rigid_body(link.GetPrim(), mass=mass)
    return link


def build_arm(path: str) -> None:
    stage = Usd.Stage.CreateNew(path)
    h.configure_stage(stage)

    root = h.add_xform(stage, "/Arm")
    h.mark_kind(root.GetPrim(), "component")
    h.set_default_prim(stage, root.GetPrim())
    phys.make_articulation_root(root.GetPrim())          # one articulated system

    # Base: a fixed post standing on the ground (origin at its foot).
    base = h.add_xform(stage, "/Arm/Base")
    h.add_disc(stage, "/Arm/Base/Post", radius=0.045, height=spec.POST_HEIGHT,
               translate=(0, spec.POST_HEIGHT / 2, 0),
               color=(0.2, 0.2, 0.22), roughness=0.5)
    phys.make_rigid_body(base.GetPrim(), mass=8.0, kinematic=True)

    # J0 yaw (Y) — Yoke at the top of the post.
    _joint_link(stage, "/Arm/Base/Yoke", translate=(0, spec.POST_HEIGHT, 0),
                axis="Y", mass=1.5)
    h.add_box(stage, "/Arm/Base/Yoke/Geo", size=(0.09, 0.06, 0.09),
              translate=(0, 0.03, 0), color=(0.85, 0.5, 0.1), roughness=0.4)

    # J1 shoulder (X) — UpperArm extends along +Z.
    _joint_link(stage, "/Arm/Base/Yoke/UpperArm", translate=(0, 0.05, 0),
                axis="X", mass=1.2)
    h.add_box(stage, "/Arm/Base/Yoke/UpperArm/Geo",
              size=(0.05, 0.05, spec.UPPERARM_LEN),
              translate=(0, 0, spec.UPPERARM_LEN / 2),
              color=(0.75, 0.75, 0.78), roughness=0.35)

    # J2 elbow (X) — Forearm at the end of the upper arm.
    _joint_link(stage, "/Arm/Base/Yoke/UpperArm/Forearm",
                translate=(0, 0, spec.UPPERARM_LEN), axis="X", mass=1.0)
    h.add_box(stage, "/Arm/Base/Yoke/UpperArm/Forearm/Geo",
              size=(0.04, 0.04, spec.FOREARM_LEN),
              translate=(0, 0, spec.FOREARM_LEN / 2),
              color=(0.75, 0.75, 0.78), roughness=0.35)

    # J3 wrist (X) — a pitch used to keep the gripper level. The gripper reaches +Z.
    gpath = "/Arm/Base/Yoke/UpperArm/Forearm/Gripper"
    _joint_link(stage, gpath, translate=(0, 0, spec.FOREARM_LEN), axis="X", mass=0.6)
    h.add_box(stage, gpath + "/Housing", size=(0.05, 0.045, 0.045),
              translate=(0, 0, 0.01), color=(0.2, 0.2, 0.22), roughness=0.4)

    # J4 roll (Z) — spins the claw about the reach axis; this is what flips the record
    # side-to-side. The claws + grasp point ride on the roll so they turn with it.
    rpath = gpath + "/Roll"
    _joint_link(stage, rpath, translate=(0, 0, 0.03), axis="Z", mass=0.3)
    # Two claws straddling the record's RIM (separated along X), reaching +Z so the
    # thin edge of the disc sits in the gap between them.
    for i, xoff in enumerate((-0.032, 0.032)):
        h.add_box(stage, f"{rpath}/Claw{i}", size=(0.014, 0.03, 0.06),
                  translate=(xoff, 0, 0.03), color=(0.15, 0.15, 0.16), roughness=0.4)
    h.add_box(stage, rpath + "/Bracket", size=(0.085, 0.025, 0.02),
              translate=(0, 0, 0.005), color=(0.15, 0.15, 0.16), roughness=0.4)
    # Pinch point between the claws (no geometry) — choreograph reads its world xform.
    gp = h.add_xform(stage, rpath + "/GraspPoint")
    h.set_translate(gp, (0, 0, 0.03))

    # --- physics joints connecting the links ------------------------------
    J = "/Arm/Joints"
    h.add_xform(stage, J)
    b_base = "/Arm/Base"
    b_yoke = "/Arm/Base/Yoke"
    b_ua = "/Arm/Base/Yoke/UpperArm"
    b_fa = "/Arm/Base/Yoke/UpperArm/Forearm"
    b_gr = gpath
    phys.add_fixed_joint(stage, J + "/BaseFix", body1=b_base)
    phys.add_revolute_joint(stage, J + "/J0_yaw", body0=b_base, body1=b_yoke,
                            axis="Y", local_pos0=(0, spec.POST_HEIGHT, 0),
                            lower=-180, upper=180)
    phys.add_revolute_joint(stage, J + "/J1_shoulder", body0=b_yoke, body1=b_ua,
                            axis="X", local_pos0=(0, 0.05, 0),
                            lower=-120, upper=60)
    phys.add_revolute_joint(stage, J + "/J2_elbow", body0=b_ua, body1=b_fa,
                            axis="X", local_pos0=(0, 0, spec.UPPERARM_LEN),
                            lower=-10, upper=150)
    phys.add_revolute_joint(stage, J + "/J3_wrist", body0=b_fa, body1=b_gr,
                            axis="X", local_pos0=(0, 0, spec.FOREARM_LEN),
                            lower=-150, upper=150)
    phys.add_revolute_joint(stage, J + "/J4_roll", body0=b_gr, body1=gpath + "/Roll",
                            axis="Z", local_pos0=(0, 0, 0.03),
                            lower=-200, upper=200)

    stage.GetRootLayer().Save()
    print("wrote", path)


def build_crate(path: str) -> None:
    stage = Usd.Stage.CreateNew(path)
    h.configure_stage(stage)

    root = h.add_xform(stage, "/Crate")
    h.mark_kind(root.GetPrim(), "component")
    h.set_default_prim(stage, root.GetPrim())

    # A shallow tray: a floor plus four low rim walls. A record lies flat inside.
    wood = (0.35, 0.24, 0.12)
    h.add_box(stage, "/Crate/Floor", size=(0.34, 0.02, 0.34),
              translate=(0, 0.01, 0), color=wood, roughness=0.7)
    rim = 0.05
    for name, size, tr in [
        ("WallN", (0.34, rim, 0.02), (0, rim / 2, 0.16)),
        ("WallS", (0.34, rim, 0.02), (0, rim / 2, -0.16)),
        ("WallE", (0.02, rim, 0.34), (0.16, rim / 2, 0)),
        ("WallW", (0.02, rim, 0.34), (-0.16, rim / 2, 0)),
    ]:
        h.add_box(stage, f"/Crate/{name}", size=size, translate=tr,
                  color=wood, roughness=0.7)

    stage.GetRootLayer().Save()
    print("wrote", path)


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    build_turntable(os.path.join(ASSETS_DIR, "turntable.usda"))
    build_record(os.path.join(ASSETS_DIR, "record.usda"))
    build_arm(os.path.join(ASSETS_DIR, "arm.usda"))
    build_crate(os.path.join(ASSETS_DIR, "crate.usda"))


if __name__ == "__main__":
    main()
