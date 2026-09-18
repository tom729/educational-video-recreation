#!/usr/bin/env python3
"""Verify an educational MP4, export frame zero, optionally flag long holds.

Requires ffprobe and ffmpeg on PATH; Python standard library only.
Hold findings are review hints, not failures: reading and answer holds can be valid.
This does not assess visual centering, safe areas, educational or mathematical truth.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    return float(numerator) / float(denominator) if separator else float(value)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-3000:].strip()}")
    return result


def scan_holds(video: Path, duration: float, threshold: float) -> list[dict]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info",
        "-i", str(video), "-map", "0:v:0", "-an",
        "-vf", f"freezedetect=n=-60dB:d={threshold}", "-f", "null", "-",
    ])
    start = None
    holds = []
    for match in re.finditer(r"lavfi\.freezedetect\.freeze_(start|end):\s*([0-9.]+)", result.stderr):
        kind, value = match.groups()
        if kind == "start":
            start = float(value)
        elif start is not None:
            end = float(value)
            holds.append({"start": start, "end": end, "seconds": round(end - start, 3)})
            start = None
    if start is not None:
        holds.append({"start": start, "end": duration, "seconds": round(duration - start, 3)})
    return holds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--duration", type=positive_float, required=True, help="intended duration in seconds")
    parser.add_argument("--width", type=positive_int, default=1080)
    parser.add_argument("--height", type=positive_int, default=1920)
    parser.add_argument("--fps", type=positive_float, default=30)
    parser.add_argument("--duration-tolerance", type=positive_float, default=.05)
    audio_mode = parser.add_mutually_exclusive_group()
    audio_mode.add_argument("--silent", action="store_true", help="require no audio stream")
    audio_mode.add_argument("--require-audio", action="store_true", help="require an audio stream; does not verify speech quality")
    parser.add_argument("--cover", type=Path, help="write the decoded first video frame to this PNG")
    parser.add_argument("--scan-holds", action="store_true", help="report likely static spans for human review")
    parser.add_argument("--hold-threshold", type=positive_float, default=3, help="seconds before a hold is reported")
    args = parser.parse_args()
    video = args.video.expanduser().resolve(strict=True)
    cover = args.cover.expanduser().resolve() if args.cover else None
    if cover and (cover == video or cover.suffix.lower() != ".png"):
        parser.error("--cover must be a separate .png path, never the input video")

    probe = run([
        "ffprobe", "-v", "error", "-count_frames", "-show_entries",
        "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration,size",
        "-of", "json", str(video),
    ])
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    visual = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not visual:
        raise RuntimeError("No video stream found")
    stream = visual[0]
    audio_streams = sum(stream.get("codec_type") == "audio" for stream in streams)
    duration = float(stream.get("duration") or metadata["format"]["duration"])
    container_duration = float(metadata["format"]["duration"])
    fps = rate(stream["avg_frame_rate"])
    nominal_fps = rate(stream["r_frame_rate"])
    frames = int(stream["nb_read_frames"])
    expected_frames = round(args.duration * args.fps)
    errors = []
    for key, expected in [("width", args.width), ("height", args.height), ("codec_name", "h264"), ("pix_fmt", "yuv420p")]:
        if stream.get(key) != expected:
            errors.append(f"{key}: {stream.get(key)} != {expected}")
    if len(visual) != 1:
        errors.append(f"expected one video stream, found {len(visual)}")
    if abs(fps - args.fps) > .01 or abs(nominal_fps - args.fps) > .01:
        errors.append(f"frame rate: average {fps}, nominal {nominal_fps}, expected {args.fps}")
    if abs(duration - args.duration) > args.duration_tolerance:
        errors.append(f"video duration: {duration} != {args.duration}")
    if abs(container_duration - args.duration) > args.duration_tolerance:
        errors.append(f"container duration: {container_duration} != {args.duration}")
    if frames != expected_frames:
        errors.append(f"decoded frames: {frames} != {expected_frames}")
    if args.silent and audio_streams:
        errors.append(f"silent export requested, found {audio_streams} audio stream(s)")
    if args.require_audio and not audio_streams:
        errors.append("narrated export requested, no audio stream found")
    if probe.stderr.strip():
        errors.append("ffprobe reported decoding errors: " + probe.stderr[-1200:].strip())

    report = {
        "video": str(video), "width": stream["width"], "height": stream["height"],
        "fps": fps, "decoded_frames": frames, "duration": duration,
        "container_duration": container_duration, "codec": stream["codec_name"],
        "pixel_format": stream["pix_fmt"], "audio_streams": audio_streams,
        "bytes": int(metadata["format"]["size"]), "errors": errors,
    }
    if not errors and cover:
        cover.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
             "-i", str(video), "-map", "0:v:0", "-frames:v", "1", "-update", "1", str(cover)])
        report["first_frame_png"] = str(cover)
    if args.scan_holds:
        report["holds_for_review"] = scan_holds(video, duration, args.hold_threshold)
        report["hold_note"] = "Review by teaching purpose; approximate detection can include subtle motion and fades."
    report["status"] = "failed" if errors else "passed"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, ZeroDivisionError, RuntimeError) as error:
        print(f"Verification error: {error}", file=sys.stderr)
        raise SystemExit(2)
