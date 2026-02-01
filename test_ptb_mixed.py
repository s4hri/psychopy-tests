#!/usr/bin/env python3
"""
PTB (Psychtoolbox) audio-only diagnostic — MIXED OVERLAP BUFFER

Plays one buffer containing overlap:
- D4 (~293.66 Hz) for 5 s (t=0)
- A4 (440 Hz) for 3 s starting at t=2 s

IMPORTANT: FillBuffer expects shape (numSamples, numChannels).

Run:
  psychopy --direct test_ptb_mixed.py
  /opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/bin/python3 test_ptb_mixed.py --verbose

Exit code: always 0 (qualitative test).
"""

import argparse
import os
import sys
import time
import platform
from pprint import pformat

RESULTS = {}


def section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def env_info():
    section("1) Runtime & environment")
    print(f"Python   : {platform.python_version()} ({sys.executable})")
    print(f"Platform : {platform.platform()}")
    print(f"User/UID : {os.getenv('USER', 'unknown')} / {os.getuid()}")
    for k in ["DISPLAY", "WAYLAND_DISPLAY", "PULSE_SERVER", "PIPEWIRE_REMOTE"]:
        v = os.environ.get(k)
        if v:
            print(f"{k:14}: {v}")


def ptb_info(verbose: bool):
    section("2) PTB / Psychtoolbox information")
    devices = []
    try:
        import psychtoolbox  # noqa: F401
        from psychtoolbox import PsychPortAudio

        print("psychtoolbox: import OK")
        try:
            ver = PsychPortAudio("Version")
            print("PsychPortAudio('Version'):")
            if verbose:
                print(pformat(ver, width=140))
            else:
                print({k: ver.get(k) for k in ["version", "date", "time", "os", "language"] if k in ver})
        except Exception as e:
            print(f"PsychPortAudio('Version') failed: {e}")

        try:
            devs = PsychPortAudio("GetDevices")
            devices = list(devs) if devs is not None else []
            RESULTS["ptb_device_query_ok"] = True
            print(f"PsychPortAudio('GetDevices'): {len(devices)} device(s) found")
            if verbose:
                print(pformat(devices, width=140))
            else:
                for d in devices:
                    idx = d.get("DeviceIndex", d.get("deviceIndex", "?"))
                    name = d.get("DeviceName", d.get("deviceName", "unknown"))
                    host = d.get("HostAudioAPIName", d.get("hostAudioAPIName", ""))
                    outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
                    inch = d.get("NrInputChannels", d.get("nrInputChannels", 0))
                    sr = d.get("DefaultSampleRate", d.get("defaultSampleRate", ""))
                    print(f"- idx={idx} name='{name}' host='{host}' out={outch} in={inch} sr={sr}")
        except Exception as e:
            RESULTS["ptb_device_query_ok"] = False
            print(f"PsychPortAudio('GetDevices') failed: {e}")
            devices = []

    except Exception as e:
        RESULTS["ptb_device_query_ok"] = False
        print(f"psychtoolbox import failed: {e}")

    return devices


def choose_output_device(devices, device_index_arg):
    if not devices:
        return None, None, None, None

    if device_index_arg is not None:
        for d in devices:
            idx = d.get("DeviceIndex", d.get("deviceIndex", None))
            if idx is not None and int(idx) == int(device_index_arg):
                name = d.get("DeviceName", d.get("deviceName", "unknown"))
                sr = float(d.get("DefaultSampleRate", d.get("defaultSampleRate", 44100.0)))
                outch = int(float(d.get("NrOutputChannels", d.get("nrOutputChannels", 2)) or 2))
                return int(idx), name, sr, outch
        print(f"WARNING: --device-index {device_index_arg} not found; falling back to auto selection.")

    for d in devices:
        outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
        if outch and float(outch) > 0:
            idx = d.get("DeviceIndex", d.get("deviceIndex", None))
            if idx is None:
                continue
            name = d.get("DeviceName", d.get("deviceName", "unknown"))
            sr = float(d.get("DefaultSampleRate", d.get("defaultSampleRate", 44100.0)))
            outch_i = int(float(outch))
            return int(idx), name, sr, outch_i

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
    return y


def mix_overlap(d_freq, d_secs, a_freq, a_secs, a_delay, sr, fade_s, peak=0.9):
    import numpy as np
    total_n = int(round(d_secs * sr))
    buf = np.zeros((total_n,), dtype=np.float32)

    d = make_tone(d_freq, d_secs, sr, fade_s)
    buf[: len(d)] += d

    start = int(round(a_delay * sr))
    a = make_tone(a_freq, a_secs, sr, fade_s)
    end = min(total_n, start + len(a))
    if start < total_n and end > start:
        buf[start:end] += a[: (end - start)]

    mx = float(np.max(np.abs(buf))) if len(buf) else 0.0
    if mx > 0:
        buf = (buf / mx) * float(peak)
    return buf


def to_channels(samples_mono, channels: int):
    import numpy as np
    x = samples_mono.astype(np.float32, copy=False)
    return np.repeat(x[:, None], channels, axis=1)  # (N, channels)


def open_ptb_stream(dev_idx: int, sr: int, channels: int, latency_class: int):
    from psychtoolbox import PsychPortAudio
    return PsychPortAudio("Open", dev_idx, 1, latency_class, sr, channels)


def play_buffer(pahandle, bufferdata, seconds_expected, label):
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
        return True
    except Exception:
        return False


def print_summary():
    section("SUMMARY")
    def flag(x): return "OK" if x else "FAIL"
    print(f"PTB device query : {flag(RESULTS.get('ptb_device_query_ok', False))}")
    print(f"PTB stream open  : {flag(RESULTS.get('stream_open_ok', False))}")
    print(f"Mixed overlap    : {flag(RESULTS.get('mixed_ok', False))}")


def main():
    ap = argparse.ArgumentParser(description="PTB audio-only diagnostic — mixed overlap buffer")
    ap.add_argument("--verbose", action="store_true", help="print verbose PTB device/config info")
    ap.add_argument("--device-index", type=int, default=None, help="PTB DeviceIndex to use (from GetDevices)")
    ap.add_argument("--sr", type=int, default=0, help="sample rate override (0 = device default)")
    ap.add_argument("--latency-class", type=int, default=1, help="PTB latency class (default 1)")
    ap.add_argument("--fade-secs", type=float, default=0.01, help="fade in/out seconds (default 0.01)")

    ap.add_argument("--d-hz", type=float, default=293.66, help="D tone frequency (default D4 ~293.66)")
    ap.add_argument("--d-secs", type=float, default=5.0, help="D tone duration seconds (default 5.0)")
    ap.add_argument("--a-hz", type=float, default=440.0, help="A tone frequency (default A4 440)")
    ap.add_argument("--a-secs", type=float, default=3.0, help="A tone duration seconds (default 3.0)")
    ap.add_argument("--a-delay", type=float, default=2.0, help="delay before A starts (default 2.0)")

    args = ap.parse_args()

    env_info()
    devices = ptb_info(verbose=args.verbose)

    section("3) Device selection")
    dev_idx, dev_name, dev_sr, dev_outch = choose_output_device(devices, args.device_index)
    if dev_idx is None:
        print("ERROR: could not select an output device from PTB list.")
        print_summary()
        return 0

    sr = args.sr if args.sr and args.sr > 0 else int(dev_sr) if dev_sr else 44100
    channels = max(1, int(dev_outch))
    print(f"Selected device: idx={dev_idx}, name='{dev_name}', defaultSR={dev_sr}, outCh={dev_outch}")
    print(f"Using sample rate: {sr} Hz")
    print(f"Using channels   : {channels}")

    section("4) TEST: mixed overlap buffer")
    print("Plan:")
    print(f"- D tone: {args.d_hz:.2f} Hz for {args.d_secs:.2f}s (t=0)")
    print(f"- A tone: {args.a_hz:.2f} Hz for {args.a_secs:.2f}s (t={args.a_delay:.2f}s)")

    pahandle = None
    try:
        pahandle = open_ptb_stream(dev_idx, sr, channels=channels, latency_class=args.latency_class)
        RESULTS["stream_open_ok"] = True

        mono = mix_overlap(args.d_hz, args.d_secs, args.a_hz, args.a_secs, args.a_delay, sr, args.fade_secs)
        buf = to_channels(mono, channels)
        RESULTS["mixed_ok"] = bool(play_buffer(pahandle, buf, args.d_secs, "Mixed overlap buffer"))

    except Exception as e:
        RESULTS["stream_open_ok"] = False
        RESULTS["mixed_ok"] = False
        print(f"PTB mixed test failed: {e}")

    finally:
        if pahandle is not None:
            close_ptb_stream(pahandle)

    print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
