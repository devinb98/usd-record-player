"""Render the stage to an image sequence + an animated GIF preview.

Uses Apple's system `usdrecord` (Hydra Storm) to rasterize frames, one explicit
filename per frame (this avoids a quirk in that build's "###" frame-placeholder
formatting), then stitches a looping GIF with Pillow. No ffmpeg required; if you
`brew install ffmpeg`, pass --mp4 to also write an .mp4.

Usage:
    python src/render.py                 # 24 sample frames -> renders/turntable.gif
    python src/render.py --frames 48 --width 1000
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess

from pxr import Usd

ROOT = os.path.join(os.path.dirname(__file__), "..")
USDRECORD = "/usr/bin/usdrecord"


def render_frames(stage_path: str, out_dir: str, *, camera: str, width: int,
                  complexity: str, n: int) -> list[str]:
    stage = Usd.Stage.Open(stage_path)
    start, end = stage.GetStartTimeCode(), stage.GetEndTimeCode()
    n = max(1, n)
    # Evenly sample the timeline as integer time codes (inclusive of both ends).
    if n > 1:
        times = sorted({round(start + (end - start) * i / (n - 1)) for i in range(n)})
    else:
        times = [round(start)]

    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".png"):
            os.remove(os.path.join(out_dir, f))

    # Apple's usdrecord ALWAYS needs a "###" placeholder and names the file after
    # the (oddly formatted) time code. So we render each frame into a cleared temp
    # dir and move whatever single PNG appears to a clean, ordered name.
    tmp = os.path.join(out_dir, "_tmp")
    paths = []
    for i, t in enumerate(times):
        if os.path.isdir(tmp):
            shutil.rmtree(tmp)
        os.makedirs(tmp)
        subprocess.run(
            [USDRECORD, "--camera", camera, "--imageWidth", str(width),
             "--complexity", complexity, "--frames", str(int(t)),
             stage_path, os.path.join(tmp, "f.###.png")],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        produced = [p for p in os.listdir(tmp) if p.endswith(".png")]
        if not produced:
            raise RuntimeError(f"usdrecord produced no image for frame {t}")
        out = os.path.join(out_dir, f"frame_{i:04d}.png")
        os.replace(os.path.join(tmp, produced[0]), out)
        paths.append(out)
        print(f"  frame {i + 1}/{len(times)}  (t={int(t)})")
    shutil.rmtree(tmp, ignore_errors=True)
    return paths


def make_gif(frame_paths: list[str], gif_path: str, fps: float) -> None:
    from PIL import Image
    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    imgs[0].save(gif_path, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / fps), loop=0, optimize=True)
    print("wrote", gif_path)


def make_mp4(out_dir: str, mp4_path: str, fps: float) -> None:
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found; skipping mp4 (brew install ffmpeg to enable)")
        return
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(fps),
         "-i", os.path.join(out_dir, "frame_%04d.png"),
         "-pix_fmt", "yuv420p", mp4_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", mp4_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=os.path.join(ROOT, "stage.usda"))
    ap.add_argument("--camera", default="Camera")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--complexity", default="high",
                    choices=["low", "medium", "high", "veryhigh"])
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--mp4", action="store_true")
    args = ap.parse_args()

    frame_dir = os.path.join(ROOT, "renders", "frames")
    paths = render_frames(args.stage, frame_dir, camera=args.camera,
                          width=args.width, complexity=args.complexity,
                          n=args.frames)
    make_gif(paths, os.path.join(ROOT, "renders", "turntable.gif"), args.fps)
    if args.mp4:
        make_mp4(frame_dir, os.path.join(ROOT, "renders", "turntable.mp4"), args.fps)


if __name__ == "__main__":
    main()
