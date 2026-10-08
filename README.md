# Robotic Record-Player Cell — an OpenUSD learning project

A hands-on project for learning **OpenUSD** by building a robotic record player, in
pure OpenUSD (the `pxr` Python API) — no Omniverse, Blender, or DCC apps. A robot arm
picks a record from a crate, places it on a turntable, and plays it; later phases flip
the record and cycle through a crate of them.

Built in checkpointed phases:

1. **Turntable** — a record spins on the platter; the tonearm swings in. ✅
2. **Robot arm** — a sim-ready `UsdPhysics` articulation picks a record from the crate
   and places it on the platter (with a baked "grasp handoff"). ✅
3. **Flip** — the arm flips the record to side B (variant sets). _(next)_
4. **Full loop** — references/instancing/sublayers + a pick-and-place state machine.

## Setup (macOS)

```bash
python3.11 -m venv .venv            # usd-core wheels need CPython <= 3.12
source .venv/bin/activate
pip install usd-core numpy Pillow
```

Viewing/validating uses the USD tools macOS already ships at `/usr/bin`
(`usdrecord`, `usdchecker`, `usdcat`) — no conda or `usdview` required.

## Build & render

```bash
./build.sh                      # assets -> stage -> choreography -> GIF (opens it)
./build.sh --frames 48 --width 1000 --mp4   # extra flags pass to render.py
```

The pipeline, if you want to run steps individually:

| Step | Script | Produces |
|---|---|---|
| Assets | `src/build_assets.py` | `assets/{turntable,record,arm,crate}.usda` |
| Static layout | `src/build_stage.py` | `stage.usda` (references, camera, lights) |
| Animation | `src/choreograph.py` | time samples: arm joints, record handoff, spin |
| Render | `src/render.py` | `renders/turntable.gif` (+ frames) |

Inspect the composed scene as text with `usdcat stage.usda`, or validate with
`usdchecker stage.usda`.

## Code map

- `src/usd_helpers.py` — authoring wrappers (materials, geometry, transforms)
- `src/physics.py` — `UsdPhysics` helpers (rigid bodies, joints, drives, articulation)
- `src/arm_spec.py` — the arm's joint chain, shared by builder + choreographer
- `src/build_assets.py` — authors the referenceable component assets
- `src/build_stage.py` — assembles the static scene
- `src/choreograph.py` — animates the arm and bakes the record handoff
- `src/render.py` — `usdrecord` + Pillow → image sequence and GIF
