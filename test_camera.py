#!/usr/bin/env python3
"""
PsychoPy camera capture sanity test.

The script automatically discovers available cameras and their supported
capture modes, selects a conservative mode, records a short clip, and saves it.

Examples
--------

List cameras and all supported modes:

    python test_camera.py --list

Record using the first available camera and an automatically selected mode:

    python test_camera.py

Use camera #1:

    python test_camera.py --device 1

Use a camera by name:

    python test_camera.py --device /dev/video2

Use a specific mode listed by --list:

    python test_camera.py --device 0 --mode 3

Record for 10 seconds:

    python test_camera.py --duration 10

Choose output file:

    python test_camera.py --output camera_test.mp4
"""

import argparse
import sys

from psychopy import core
from psychopy.hardware.camera import Camera, CameraDevice


DEFAULT_DURATION = 5.0
DEFAULT_OUTPUT = "test_video.mp4"


def get_profiles():
    """Return all camera profiles reported by PsychoPy."""
    profiles = CameraDevice.getAvailableDevices(best=False)

    if not profiles:
        raise RuntimeError("No camera devices detected by PsychoPy.")

    return profiles


def get_camera_names(profiles):
    """Return unique physical camera names, preserving discovery order."""
    return list(dict.fromkeys(
        profile["deviceName"] for profile in profiles
    ))


def get_camera_profiles(profiles, camera_name):
    """Return all modes belonging to one physical camera."""
    return [
        profile
        for profile in profiles
        if profile["deviceName"] == camera_name
    ]


def mode_description(profile):
    """Return a compact human-readable description of a camera mode."""
    width, height = profile["frameSize"]

    pixel_format = profile.get("pixelFormat")
    codec_format = profile.get("codecFormat")

    fmt = pixel_format or codec_format or "unknown"

    return (
        f"{width}x{height} @ {profile['frameRate']} fps, "
        f"format={fmt}, "
        f"backend={profile['captureLib']}, "
        f"API={profile['captureAPI']}"
    )


def list_cameras(profiles):
    """Print all detected cameras and supported modes."""
    camera_names = get_camera_names(profiles)

    print(f"Found {len(camera_names)} camera(s).\n")

    for camera_index, camera_name in enumerate(camera_names):
        camera_profiles = get_camera_profiles(
            profiles,
            camera_name,
        )

        print(f"[{camera_index}] {camera_name}")

        for mode_index, profile in enumerate(camera_profiles):
            print(
                f"    mode {mode_index}: "
                f"{mode_description(profile)}"
            )

        print()


def resolve_camera(profiles, device):
    """
    Resolve --device.

    `device` can be:
      - None -> first camera
      - numeric index -> camera index from --list
      - exact device name -> e.g. /dev/video0
    """
    camera_names = get_camera_names(profiles)

    if device is None:
        return camera_names[0]

    # Numeric camera index
    try:
        index = int(device)

        if index < 0 or index >= len(camera_names):
            raise ValueError(
                f"Camera index {index} does not exist. "
                f"Available range: 0..{len(camera_names) - 1}"
            )

        return camera_names[index]

    except ValueError:
        pass

    # Exact camera name
    if device in camera_names:
        return device

    raise ValueError(
        f"Camera '{device}' not found. "
        "Use --list to see available cameras."
    )


def select_mode(profiles):
    """
    Automatically select a conservative camera mode.

    The purpose is compatibility rather than maximum image quality.

    Preference:
      1. ffpyplayer backend
      2. raw/uncompressed pixel format
      3. >= 30 fps
      4. resolution <= 640x480
      5. highest resolution
      6. highest frame rate

    If a preferred category is unavailable, the selector falls back to the
    modes actually supported by the camera.
    """
    candidates = list(profiles)

    # Prefer ffpyplayer, since this is the backend used by this test.
    ffpy_modes = [
        p for p in candidates
        if p.get("captureLib") == "ffpyplayer"
    ]

    if ffpy_modes:
        candidates = ffpy_modes

    # Prefer raw/uncompressed formats when available.
    raw_modes = [
        p for p in candidates
        if p.get("pixelFormat")
        and not p.get("codecFormat")
    ]

    if raw_modes:
        candidates = raw_modes

    # Prefer approximately 30 fps or better.
    realtime_modes = [
        p for p in candidates
        if float(p["frameRate"]) >= 29.0
    ]

    if realtime_modes:
        candidates = realtime_modes

    # Prefer a modest resolution for a hardware sanity test.
    moderate_modes = [
        p for p in candidates
        if (
            p["frameSize"][0] <= 640
            and p["frameSize"][1] <= 480
        )
    ]

    if moderate_modes:
        candidates = moderate_modes

    # Among remaining candidates choose highest resolution,
    # then highest frame rate.
    return max(
        candidates,
        key=lambda p: (
            p["frameSize"][0] * p["frameSize"][1],
            float(p["frameRate"]),
        ),
    )


def create_camera(profile):
    """Create a PsychoPy Camera using one exact advertised profile."""
    camera_device = CameraDevice(
        device=profile["deviceName"],
        captureLib=profile["captureLib"],
        frameSize=profile["frameSize"],
        frameRate=profile["frameRate"],
        pixelFormat=profile.get("pixelFormat"),
        codecFormat=profile.get("codecFormat"),
        captureAPI=profile.get("captureAPI"),
    )

    return Camera(device=camera_device)


def record_video(profile, duration, output):
    """Open, record, save and close the camera."""

    print("\nSelected configuration:")
    print(f"  Device:       {profile['deviceName']}")
    print(f"  Backend:      {profile['captureLib']}")
    print(f"  Capture API:  {profile['captureAPI']}")
    print(f"  Resolution:   {profile['frameSize']}")
    print(f"  Frame rate:   {profile['frameRate']}")
    print(f"  Pixel format: {profile.get('pixelFormat')}")
    print(f"  Codec format: {profile.get('codecFormat')}")
    print()

    cam = create_camera(profile)

    try:
        print("Opening camera...")
        cam.open()

        print(f"Recording {duration:.1f} seconds...")
        cam.record()

        clock = core.Clock()

        while clock.getTime() < duration:
            cam.poll()
            core.wait(0.001)

        print("Stopping...")
        cam.stop()

        print(f"Saving: {output}")
        cam.save(
            output,
            useThreads=False,
        )

        print(f"Done: {output}")

    finally:
        cam.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="PsychoPy camera capture sanity test."
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List detected cameras and all supported modes, then exit.",
    )

    parser.add_argument(
        "--device",
        default=None,
        help=(
            "Camera to use. Can be the camera number shown by --list "
            "or an exact device name such as /dev/video0. "
            "Default: first detected camera."
        ),
    )

    parser.add_argument(
        "--mode",
        type=int,
        default=None,
        help=(
            "Camera mode number shown by --list. "
            "Default: automatically select a conservative supported mode."
        ),
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION,
        help=f"Recording duration in seconds. Default: {DEFAULT_DURATION}.",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output MP4 filename. Default: {DEFAULT_OUTPUT}.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.duration <= 0:
        print("ERROR: --duration must be greater than zero.", file=sys.stderr)
        return 1

    try:
        profiles = get_profiles()

        if args.list:
            list_cameras(profiles)
            return 0

        camera_name = resolve_camera(
            profiles,
            args.device,
        )

        camera_profiles = get_camera_profiles(
            profiles,
            camera_name,
        )

        print(f"Using camera: {camera_name}")
        print(
            f"Camera exposes "
            f"{len(camera_profiles)} supported mode(s)."
        )

        if args.mode is not None:
            if (
                args.mode < 0
                or args.mode >= len(camera_profiles)
            ):
                raise ValueError(
                    f"Mode {args.mode} does not exist for "
                    f"{camera_name}. Available range: "
                    f"0..{len(camera_profiles) - 1}"
                )

            profile = camera_profiles[args.mode]

            print(f"Using explicitly selected mode {args.mode}.")

        else:
            profile = select_mode(camera_profiles)

            # Find its displayed mode number for reproducibility.
            mode_index = camera_profiles.index(profile)

            print(
                f"Automatically selected mode {mode_index}."
            )
            print(
                "To force this configuration in future runs, use "
                f"--device {get_camera_names(profiles).index(camera_name)} "
                f"--mode {mode_index}"
            )

        record_video(
            profile,
            args.duration,
            args.output,
        )

        return 0

    except Exception as err:
        print(f"\nERROR: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())