"""
Composite the two raw recordings (assets/recording_raw/dom.webm and
webmcp.webm) into a single side-by-side video with labels, for use in the
README and as a LinkedIn/social clip.

Labels are pre-rendered as PNG images with Pillow (this ffmpeg build has
no drawtext/libfreetype support), then composited with vstack/hstack.
Both looped label image inputs and both scaled video streams get an
explicit duration (`-t`) matching the final output length -- letting
ffmpeg infer duration from `-shortest` across a mix of finite video
streams and infinitely-looped image streams was hanging/timing out, so
duration is computed up front in Python instead.

Requires ffmpeg on PATH.

Outputs:
  assets/side_by_side_demo.mp4  (for LinkedIn / general sharing)
  assets/side_by_side_demo.gif  (renders inline & autoplays on GitHub READMEs)
"""
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent.parent / "assets"
RAW_DIR = ASSETS_DIR / "recording_raw"
DOM_VIDEO = RAW_DIR / "dom.webm"
WEBMCP_VIDEO = RAW_DIR / "webmcp.webm"
OUT_MP4 = ASSETS_DIR / "side_by_side_demo.mp4"
OUT_GIF = ASSETS_DIR / "side_by_side_demo.gif"

PANEL_W = 800
PANEL_H = 900
LABEL_BAR_H = 60
GAP_W = 8

DOM_LABEL_PATH = ASSETS_DIR / "_dom_label.png"
WEBMCP_LABEL_PATH = ASSETS_DIR / "_webmcp_label.png"

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

HOLD_ON_SUCCESS_SEC = 3  # extra seconds to hold the last frame of the shorter clip


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def make_label_bar(path: Path, text: str, bg_color: str):
    img = Image.new("RGB", (PANEL_W, LABEL_BAR_H), bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 26)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (PANEL_W - text_w) / 2
    y = (LABEL_BAR_H - text_h) / 2 - bbox[1]
    draw.text((x, y), text, fill="white", font=font)
    img.save(path)


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`) and retry.")


def compose_mp4():
    make_label_bar(DOM_LABEL_PATH, "DOM ACTUATION (plain clicking/typing)", "#d93025")
    make_label_bar(WEBMCP_LABEL_PATH, "WEBMCP (structured tool calls)", "#188038")

    dom_dur = probe_duration(DOM_VIDEO)
    webmcp_dur = probe_duration(WEBMCP_VIDEO)
    total_dur = max(dom_dur, webmcp_dur) + HOLD_ON_SUCCESS_SEC
    dom_pad = total_dur - dom_dur
    webmcp_pad = total_dur - webmcp_dur

    print(f"dom={dom_dur:.1f}s webmcp={webmcp_dur:.1f}s -> total={total_dur:.1f}s")

    filter_complex = f"""
    [0:v]scale={PANEL_W}:{PANEL_H},tpad=stop_mode=clone:stop_duration={dom_pad:.2f}[dom_scaled];
    [1:v]scale={PANEL_W}:{PANEL_H},tpad=stop_mode=clone:stop_duration={webmcp_pad:.2f}[webmcp_scaled];
    [2:v][dom_scaled]vstack=inputs=2[dom_panel];
    [3:v][webmcp_scaled]vstack=inputs=2[webmcp_panel];
    color=c=0x202124:s={GAP_W}x{PANEL_H + LABEL_BAR_H}:d={total_dur:.2f}[gap];
    [dom_panel][gap][webmcp_panel]hstack=inputs=3[out]
    """.strip()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(DOM_VIDEO),
        "-i", str(WEBMCP_VIDEO),
        "-loop", "1", "-t", f"{total_dur:.2f}", "-i", str(DOM_LABEL_PATH),
        "-loop", "1", "-t", f"{total_dur:.2f}", "-i", str(WEBMCP_LABEL_PATH),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", f"{total_dur:.2f}",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        raise RuntimeError("ffmpeg mp4 composition failed")
    print(f"MP4 saved: {OUT_MP4}")

    DOM_LABEL_PATH.unlink(missing_ok=True)
    WEBMCP_LABEL_PATH.unlink(missing_ok=True)


def compose_gif():
    palette = ASSETS_DIR / "_palette.png"
    scale_filter = "scale=900:-1:flags=lanczos"

    r1 = subprocess.run(
        ["ffmpeg", "-y", "-i", str(OUT_MP4),
         "-vf", f"{scale_filter},fps=12,palettegen=stats_mode=diff",
         str(palette)],
        capture_output=True, text=True, timeout=45,
    )
    if r1.returncode != 0:
        print(r1.stderr[-2000:])
        raise RuntimeError("palettegen failed")

    r2 = subprocess.run(
        ["ffmpeg", "-y", "-i", str(OUT_MP4), "-i", str(palette),
         "-filter_complex", f"{scale_filter},fps=12[x];[x][1:v]paletteuse=dither=bayer",
         str(OUT_GIF)],
        capture_output=True, text=True, timeout=45,
    )
    if r2.returncode != 0:
        print(r2.stderr[-2000:])
        raise RuntimeError("paletteuse failed")

    palette.unlink(missing_ok=True)
    print(f"GIF saved: {OUT_GIF}")


def main():
    check_ffmpeg()
    if not DOM_VIDEO.exists() or not WEBMCP_VIDEO.exists():
        raise FileNotFoundError(
            "Raw recordings not found. Run harness/record_demo.py first."
        )
    compose_mp4()
    compose_gif()

    mp4_size = OUT_MP4.stat().st_size / (1024 * 1024)
    gif_size = OUT_GIF.stat().st_size / (1024 * 1024)
    print(f"\nMP4: {mp4_size:.1f} MB")
    print(f"GIF: {gif_size:.1f} MB")


if __name__ == "__main__":
    main()
