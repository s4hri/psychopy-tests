#!/usr/bin/env python3
"""
PTB stereo channel separation and mix test (single device).

Plays three stereo buffers on one output device:
1. Left channel: D4 (~293.66 Hz) for N seconds, right channel silent
2. Right channel: A4 (440 Hz) for M seconds, left channel silent
3. Both channels: D4 on left, A4 on right, played simultaneously for max(N, M) seconds

This is a qualitative test to verify:
- the device plays stereo
- left/right channel separation works (no overlap)
- both channels can play simultaneously without crosstalk

Run:
    psychopy --direct test_ptb_stereo_mix.py
    /opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/lib/python3.10 test_ptb_stereo_mix.py --list-devices
    /opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/lib/python3.10 test_ptb_stereo_mix.py --device-index 1

Exit code: always 0.
"""

import argparse
import os
import sys
import time
import platform
from pprint import pformat

RESULTS = {}

def build_stereo_mix_buffer(sr: int, d_hz: float, d_secs: float, a_hz: float, a_secs: float, fade_s: float):
    """
    Return bufferdata shaped (numSamples, 2) where:
    - left contains D tone for d_secs
    - right contains A tone for a_secs
    Both start at t=0, duration = max(d_secs, a_secs)
    """
    import numpy as np
    n = int(round(max(d_secs, a_secs) * sr))
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)
    d = make_tone(d_hz, d_secs, sr, fade_s)
    a = make_tone(a_hz, a_secs, sr, fade_s)
    left[:len(d)] = d
    right[:len(a)] = a
    stereo = np.stack([left, right], axis=1)
    mx = float(np.max(np.abs(stereo)))
    if mx > 0:
        stereo *= 0.9 / mx
    return stereo

def section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def env_info():
    section("Runtime & environment")
    print(f"Python   : {platform.python_version()} ({sys.executable})")
    print(f"Platform : {platform.platform()}")
    print(f"User/UID : {os.getenv('USER', 'unknown')} / {os.getuid()}")
    for k in ["DISPLAY", "WAYLAND_DISPLAY", "PULSE_SERVER", "PIPEWIRE_REMOTE"]:
        v = os.environ.get(k)
        if v:
            print(f"{k:14}: {v}")


def parse_args_direct_friendly(ap: argparse.ArgumentParser):
    argv = sys.argv[1:]
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    return ap.parse_args(argv)


def ptb_get_devices(verbose: bool):
    devices = []
    try:
        from psychtoolbox import PsychPortAudio
        _ = PsychPortAudio("Version")  # prints PTB-INFO on many builds
        devs = PsychPortAudio("GetDevices")
        devices = list(devs) if devs is not None else []
        if verbose:
            print(pformat(devices, width=140))
        RESULTS["ptb_device_query_ok"] = True
        return devices
    except Exception as e:
        print(f"PTB GetDevices failed: {e}")
        RESULTS["ptb_device_query_ok"] = False
        return []


def ptb_print_devices(devices):
    section("PTB devices")
    if not devices:
        print("No devices found (or PTB unavailable).")
        return
    for d in devices:
        idx = d.get("DeviceIndex", d.get("deviceIndex", "?"))
        name = d.get("DeviceName", d.get("deviceName", "unknown"))
        host = d.get("HostAudioAPIName", d.get("hostAudioAPIName", ""))
        outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
        inch = d.get("NrInputChannels", d.get("nrInputChannels", 0))
        sr = d.get("DefaultSampleRate", d.get("defaultSampleRate", ""))
        print(f"- idx={idx} name='{name}' host='{host}' out={outch} in={inch} sr={sr}")


def choose_output_device(devices, device_index_arg):
    if not devices:
        return None, None, None, None

    if device_index_arg is not None:
        for d in devices:
            idx = d.get("DeviceIndex", d.get("deviceIndex", None))
            if idx is not None and int(float(idx)) == int(device_index_arg):
                name = d.get("DeviceName", d.get("deviceName", "unknown"))
                sr = float(d.get("DefaultSampleRate", d.get("defaultSampleRate", 44100.0)))
                outch = int(float(d.get("NrOutputChannels", d.get("nrOutputChannels", 2)) or 2))
                return int(device_index_arg), name, int(sr), outch
        print(f"WARNING: --device-index {device_index_arg} not found; falling back to auto selection.")

    # auto: first device with output channels
    for d in devices:
        outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
        if outch and float(outch) > 0:
            idx = d.get("DeviceIndex", d.get("deviceIndex", None))
            if idx is None:
                continue
            name = d.get("DeviceName", d.get("deviceName", "unknown"))
            sr = float(d.get("DefaultSampleRate", d.get("defaultSampleRate", 44100.0)))
            return int(float(idx)), name, int(sr), int(float(outch))

    return None, None, None, None


def make_tone(freq_hz: float, dur_s: float, sr: int, fade_s: float):
    import numpy as np
    n = int(round(dur_s * sr))
    t = (np.arange(n, dtype=np.float32) / float(sr)).astype(np.float32)
    y = np.sin(2.0 * np.pi * float(freq_hz) * t).astype(np.float32)

    fn = int(round(fade_s * sr))
    fn = max(0, min(fn, n // 2))
    if fn > 0:
        ramp = np.linspace(0.0, 1.0, fn, dtype=np.float32)
        y[:fn] *= ramp
        y[-fn:] *= ramp[::-1]
    return y  # (N,)


def build_stereo_buffer(sr: int, d_hz: float, d_secs: float, a_hz: float, a_secs: float, fade_s: float):
    def build_stereo_mix_buffer(sr: int, d_hz: float, d_secs: float, a_hz: float, a_secs: float, fade_s: float):
        """
        Return bufferdata shaped (numSamples, 2) where:
        - left contains D tone for d_secs
        - right contains A tone for a_secs
        Both start at t=0, duration = max(d_secs, a_secs)
        """
        import numpy as np
        n = int(round(max(d_secs, a_secs) * sr))
        left = np.zeros(n, dtype=np.float32)
        right = np.zeros(n, dtype=np.float32)
        d = make_tone(d_hz, d_secs, sr, fade_s)
        a = make_tone(a_hz, a_secs, sr, fade_s)
        left[:len(d)] = d
        right[:len(a)] = a
        stereo = np.stack([left, right], axis=1)
        mx = float(np.max(np.abs(stereo)))
        if mx > 0:
            stereo *= 0.9 / mx
        return stereo
    """
    Return bufferdata shaped (numSamples, 2) where:
    - left contains D tone for d_secs, right is silent
    - then right contains A tone for a_secs, left is silent
    """
    import numpy as np

    left = make_tone(d_hz, d_secs, sr, fade_s)
    right = make_tone(a_hz, a_secs, sr, fade_s)

    # First segment: left plays, right silent
    seg1 = np.stack([left, np.zeros_like(left)], axis=1)
    # Second segment: right plays, left silent
    seg2 = np.stack([np.zeros_like(right), right], axis=1)

    # Concatenate
    stereo = np.concatenate([seg1, seg2], axis=0).astype(np.float32)

    # Normalize to avoid clipping
    mx = float(np.max(np.abs(stereo)))
    if mx > 0:
        stereo *= 0.9 / mx

    return stereo


def open_ptb_stream(dev_idx: int, sr: int, channels: int, latency_class: int):
    from psychtoolbox import PsychPortAudio
    return PsychPortAudio("Open", int(dev_idx), 1, int(latency_class), float(sr), int(channels))


def play_ptb_buffer(pahandle, bufferdata, seconds_expected, label):
    from psychtoolbox import PsychPortAudio
    try:
        PsychPortAudio("FillBuffer", pahandle, bufferdata)
        t0 = time.time()
        PsychPortAudio("Start", pahandle, 1, 0, 1)
        time.sleep(max(0.0, seconds_expected + 0.1))
        PsychPortAudio("Stop", pahandle, 1)
        t1 = time.time()
        print(f"{label}: played (wall ≈ {t1 - t0:.2f}s)")
        return True
    except Exception as e:
        print(f"{label}: failed: {e}")
        return False


def close_ptb_stream(pahandle):
    from psychtoolbox import PsychPortAudio
    try:
        PsychPortAudio("Stop", pahandle, 1)
    except Exception:
        pass
    try:
        PsychPortAudio("Close", pahandle)
    except Exception:
        pass


def print_summary():
    section("SUMMARY")
    def flag(x): return "OK" if x else "FAIL"
    print(f"PTB device query : {flag(RESULTS.get('ptb_device_query_ok', False))}")
    print(f"PTB stream open  : {flag(RESULTS.get('stream_open_ok', False))}")
    print(f"Stereo mix play  : {flag(RESULTS.get('play_ok', False))}")


def main():

    ap = argparse.ArgumentParser(description="PTB stereo channel separation test (single device)")
    ap.add_argument("--list-devices", action="store_true", help="list PTB devices and exit")
    ap.add_argument("--verbose", action="store_true", help="verbose PTB device info")
    ap.add_argument("--device-index", type=int, default=None, help="PTB DeviceIndex to use (from GetDevices)")
    ap.add_argument("--latency-class", type=int, default=1, help="PTB latency class (default 1)")
    ap.add_argument("--fade-secs", type=float, default=0.01, help="fade in/out seconds (default 0.01)")
    ap.add_argument("--d-hz", type=float, default=293.66, help="Left channel D tone frequency (default D4 ~293.66)")
    ap.add_argument("--d-secs", type=float, default=3.0, help="Left channel D tone duration (default 3.0)")
    ap.add_argument("--a-hz", type=float, default=440.0, help="Right channel A tone frequency (default 440)")
    ap.add_argument("--a-secs", type=float, default=3.0, help="Right channel A tone duration (default 3.0)")

    args = parse_args_direct_friendly(ap)

    env_info()
    devices = ptb_get_devices(verbose=args.verbose)
    ptb_print_devices(devices)

    if args.list_devices:
        return 0

    section("Device selection")
    dev_idx, dev_name, dev_sr, dev_outch = choose_output_device(devices, args.device_index)
    if dev_idx is None:
        print("ERROR: could not select an output device.")
        print_summary()
        return 0

    # We want stereo. If device has >=2 output channels, open 2.
    if dev_outch < 2:
        print(f"ERROR: selected device reports outCh={dev_outch} (<2). Need stereo output.")
        print_summary()
        return 0

    sr = int(dev_sr) if dev_sr else 44100
    channels = 2
    print(f"Selected device: idx={dev_idx}, name='{dev_name}', defaultSR={dev_sr}, outCh={dev_outch}")
    print(f"Using sample rate: {sr} Hz")
    print(f"Opening channels : {channels} (stereo)")

    section("Test plan")
    print("Left channel: D tone, right silent")
    print(f"- freq={args.d_hz:.2f} Hz, dur={args.d_secs:.2f}s, right channel silent")
    print("Right channel: A tone, left silent")
    print(f"- freq={args.a_hz:.2f} Hz, dur={args.a_secs:.2f}s, left channel silent")
    print("Both channels: D on left, A on right, simultaneous")
    print(f"- D: freq={args.d_hz:.2f} Hz, dur={args.d_secs:.2f}s | A: freq={args.a_hz:.2f} Hz, dur={args.a_secs:.2f}s")
    print("Expected: You should hear D on LEFT only, then A on RIGHT only, then both together in their own channels.")

    pahandle = None
    try:
        pahandle = open_ptb_stream(dev_idx, sr, channels=channels, latency_class=args.latency_class)
        RESULTS["stream_open_ok"] = True

        # Sequential: left only, then right only
        buf_seq = build_stereo_buffer(
            sr=sr,
            d_hz=args.d_hz,
            d_secs=args.d_secs,
            a_hz=args.a_hz,
            a_secs=args.a_secs,
            fade_s=args.fade_secs,
        )
        total_secs_seq = args.d_secs + args.a_secs
        ok_seq = play_ptb_buffer(pahandle, buf_seq, total_secs_seq, "Stereo sequential buffer")

        # Simultaneous: both tones in their own channels
        buf_mix = build_stereo_mix_buffer(
            sr=sr,
            d_hz=args.d_hz,
            d_secs=args.d_secs,
            a_hz=args.a_hz,
            a_secs=args.a_secs,
            fade_s=args.fade_secs,
        )
        total_secs_mix = max(args.d_secs, args.a_secs)
        ok_mix = play_ptb_buffer(pahandle, buf_mix, total_secs_mix, "Stereo simultaneous buffer")

        RESULTS["play_ok"] = ok_seq and ok_mix

    except Exception as e:
        print(f"Stereo mix test failed: {e}")
        RESULTS["stream_open_ok"] = False
        RESULTS["play_ok"] = False

    finally:
        section("Cleanup")
        if pahandle is not None:
            close_ptb_stream(pahandle)

    print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
