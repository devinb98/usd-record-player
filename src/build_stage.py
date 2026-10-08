"""Phase 2 stage: the STATIC layout (no animation).

Separation of concerns (this is how real USD pipelines are organised, and sets up
Phase 4's sublayers): this file places the assets and sets up camera + lights; all
time-varying data — platter spin, tonearm, arm joints, the record handoff — is
authored by `choreograph.py` on top of this stage.

Scene layout (world space):
  /Cell
    Turntable  -> assets/turntable.usda   (at origin)
    Arm        -> assets/arm.usda          (behind-left)
    Crate      -> assets/crate.usda        (left)
    Records/Record0 -> assets/record.usda  (NEUTRAL group; its world transform is
                       baked over time by choreograph: crate -> gripper -> platter)
    Lights, Camera
"""

from __future__ import annotations

import os

from pxr import Usd, UsdGeom, UsdLux, Gf

import usd_helpers as h

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "assets")

FPS = 24.0
START, END = 1.0, 312.0          # 13 seconds — pick-and-place, then flip to side B

# Placement of the main pieces (world space). Shared intent with choreograph.py.
ARM_POS = Gf.Vec3d(-0.12, 0.0, -0.42)
CRATE_POS = Gf.Vec3d(-0.42, 0.0, -0.02)
# Where a record rests when lying in the crate (world space).
CRATE_PICK = Gf.Vec3d(-0.42, 0.055, -0.02)


def _relref(stage: Usd.Stage, asset_abspath: str) -> str:
    stage_dir = os.path.dirname(stage.GetRootLayer().realPath)
    return os.path.relpath(asset_abspath, stage_dir)


def _reference(stage, prim_path, asset_name, translate=None):
    prim = UsdGeom.Xform.Define(stage, prim_path)
    prim.GetPrim().GetReferences().AddReference(
        _relref(stage, os.path.join(ASSETS, asset_name)))
    if translate is not None:
        prim.AddTranslateOp().Set(translate)
    return prim


def build(stage_path: str) -> None:
    stage = Usd.Stage.CreateNew(stage_path)
    h.configure_stage(stage, fps=FPS, start=START, end=END)

    cell = h.add_xform(stage, "/Cell")
    h.mark_kind(cell.GetPrim(), "assembly")
    h.set_default_prim(stage, cell.GetPrim())

    # --- referenced assets -------------------------------------------------
    _reference(stage, "/Cell/Turntable", "turntable.usda")
    _reference(stage, "/Cell/Arm", "arm.usda", translate=ARM_POS)
    _reference(stage, "/Cell/Crate", "crate.usda", translate=CRATE_POS)

    # Record lives under a NEUTRAL (identity) group so its local transform == world.
    h.add_xform(stage, "/Cell/Records")
    rec = _reference(stage, "/Cell/Records/Record0", "record.usda")
    # Static initial pose: lying flat in the crate. choreograph.py time-samples this
    # same xformOp:transform to move it crate -> gripper -> platter.
    m = Gf.Matrix4d().SetTranslate(CRATE_PICK)
    UsdGeom.Xformable(rec).AddTransformOp().Set(m)
    # The stage chooses which album this record is (variant selection per instance).
    rec.GetPrim().GetVariantSet("album").SetVariantSelection("Classic")

    # --- lighting ----------------------------------------------------------
    h.add_xform(stage, "/Cell/Lights")
    UsdLux.DomeLight.Define(stage, "/Cell/Lights/Dome").CreateIntensityAttr(1.0)
    key = UsdLux.DistantLight.Define(stage, "/Cell/Lights/Key")
    key.CreateIntensityAttr(3.0)
    key.CreateAngleAttr(1.0)
    UsdGeom.Xformable(key).AddRotateXYZOp().Set(Gf.Vec3f(-45, 25, 0))

    # --- camera: wide 3/4 shot taking in crate, arm and turntable ----------
    cam = UsdGeom.Camera.Define(stage, "/Cell/Camera")
    cam.CreateFocalLengthAttr(28.0)
    cam.CreateFocusDistanceAttr(1.0)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100.0))
    eye = Gf.Vec3d(0.62, 0.55, 0.78)
    center = Gf.Vec3d(-0.14, 0.10, -0.10)
    cam2world = Gf.Matrix4d().SetLookAt(eye, center, Gf.Vec3d(0, 1, 0)).GetInverse()
    UsdGeom.Xformable(cam).AddTransformOp().Set(cam2world)

    stage.GetRootLayer().Save()
    print("wrote", stage_path)


def main() -> None:
    build(os.path.join(ROOT, "stage.usda"))


if __name__ == "__main__":
    main()
