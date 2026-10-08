"""Small, reusable OpenUSD authoring helpers.

These wrap a handful of common `pxr` patterns so the phase scripts stay readable.
Everything here uses only the official OpenUSD Python API (the `pxr` package from
`usd-core`) — no DCC apps, no solver libraries.

Mental model you'll see repeated:
  * A *stage* is an in-memory scenegraph backed by one or more *layers* (files).
  * A *prim* is a node in that graph (an Xform, a Mesh, a Material, ...).
  * *Attributes* hold typed values; they can be a single value or *time samples*.
"""

from __future__ import annotations

from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Kind


# --- units / stage conventions -------------------------------------------------

def configure_stage(stage: Usd.Stage, *, fps: float = 24.0,
                    start: float = 1.0, end: float = 1.0) -> None:
    """Apply the conventions we use everywhere: Y-up, meters, and a timeline.

    Up-axis and metersPerUnit are *stage metadata*. Getting them right up front
    means every downstream tool (usdview, usdrecord, Quick Look) agrees on which
    way is up and how big a unit is.
    """
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)  # 1 unit == 1 meter
    stage.SetTimeCodesPerSecond(fps)
    stage.SetFramesPerSecond(fps)
    stage.SetStartTimeCode(start)
    stage.SetEndTimeCode(end)


def set_default_prim(stage: Usd.Stage, prim: Usd.Prim) -> None:
    """Mark the prim that gets pulled in when this layer is *referenced*.

    A referenceable asset needs a defaultPrim so consumers know its root.
    """
    stage.SetDefaultPrim(prim)


def mark_kind(prim: Usd.Prim, kind: str) -> None:
    """Set the model `kind` (component/assembly/group) — the model hierarchy.

    `kind` is pipeline metadata that tools use to know "this subtree is one
    publishable asset". We use `component` for leaf assets like the turntable.
    """
    Usd.ModelAPI(prim).SetKind(kind)


# --- materials -----------------------------------------------------------------

def make_preview_material(stage: Usd.Stage, path: str, *,
                          color=(0.5, 0.5, 0.5), roughness: float = 0.5,
                          metallic: float = 0.0) -> UsdShade.Material:
    """Create a UsdPreviewSurface material — the portable PBR shader.

    UsdPreviewSurface is the standard "works everywhere" shader. The graph is:
        Material.surface  <--  Shader(UsdPreviewSurface).surface
    with diffuseColor / roughness / metallic as inputs.
    """
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Preview")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    # Connect the shader's surface output to the material's surface terminal.
    material.CreateSurfaceOutput().ConnectToSource(
        shader.ConnectableAPI(), "surface")
    return material


def bind_material(prim: Usd.Prim, material: UsdShade.Material) -> None:
    """Bind a material to a gprim (applies the MaterialBindingAPI schema)."""
    UsdShade.MaterialBindingAPI.Apply(prim)
    UsdShade.MaterialBindingAPI(prim).Bind(material)


# --- geometry (implicit "quadric" gprims keep Phase 1 simple) ------------------

def add_disc(stage: Usd.Stage, path: str, *, radius: float, height: float,
             translate=(0.0, 0.0, 0.0), color=(0.1, 0.1, 0.1),
             roughness: float = 0.3, metallic: float = 0.0) -> UsdGeom.Cylinder:
    """A flat disc = a Y-axis cylinder with small height. Used for platter/vinyl.

    We author it as a UsdGeom.Cylinder (an *implicit* surface) rather than a mesh:
    less data, and Hydra renders it directly. `axis='Y'` lays it flat under Y-up.
    """
    disc = UsdGeom.Cylinder.Define(stage, path)
    disc.CreateAxisAttr(UsdGeom.Tokens.y)
    disc.CreateRadiusAttr(radius)
    disc.CreateHeightAttr(height)
    # extent must be authored for implicit gprims so bbox/culling work.
    disc.CreateExtentAttr([(-radius, -height / 2, -radius),
                           (radius, height / 2, radius)])
    if translate != (0.0, 0.0, 0.0):
        UsdGeom.Xformable(disc).AddTranslateOp().Set(Gf.Vec3d(*translate))
    mat = make_preview_material(stage, path + "_mat",
                                color=color, roughness=roughness, metallic=metallic)
    bind_material(disc.GetPrim(), mat)
    return disc


def add_box(stage: Usd.Stage, path: str, *, size=(1.0, 1.0, 1.0),
            translate=(0.0, 0.0, 0.0), color=(0.5, 0.5, 0.5),
            roughness: float = 0.6) -> UsdGeom.Cube:
    """An axis-aligned box: a unit UsdGeom.Cube with a translate then scale op.

    Op ORDER matters: xformOpOrder is [translate, scale] so the translation stays
    in the parent's units. The reverse ([scale, translate]) would multiply the
    translation by the scale — a classic USD footgun.
    """
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    cube.CreateExtentAttr([(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
    xf = UsdGeom.Xformable(cube)
    xf.AddTranslateOp().Set(Gf.Vec3d(*translate))   # translate FIRST
    xf.AddScaleOp().Set(Gf.Vec3f(*size))            # scale SECOND
    mat = make_preview_material(stage, path + "_mat", color=color, roughness=roughness)
    bind_material(cube.GetPrim(), mat)
    return cube


# --- transforms ----------------------------------------------------------------

def add_xform(stage: Usd.Stage, path: str) -> UsdGeom.Xform:
    """Define an Xform (a transformable grouping prim)."""
    return UsdGeom.Xform.Define(stage, path)


def set_translate(xformable, translation) -> None:
    """Add a single translate op (static)."""
    UsdGeom.Xformable(xformable).AddTranslateOp().Set(Gf.Vec3d(*translation))
