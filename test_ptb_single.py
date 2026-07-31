#!/usr/bin/env python3
"""
PTB (Psychtoolbox) audio-only diagnostic — SINGLE BEEP

Steps:
1) Print PTB config + device list.
2) Select output device (auto by policy, or --device-index / --device-name).
3) Open ONE PTB output stream.
4) FillBuffer with correct shape (numSamples, numChannels).
5) Play beep (default 440 Hz, 1.0 s).
6) Close stream + summary.

Device selection (auto, when no explicit override given), first match wins:
  1) a device named 'default'    (ALSA default PCM -> Pulse -> system sink)
  2) a device named 'sysdefault'
  3) the first analog hw: output, excluding HDMI / NVIDIA (the real onboard
     output on machines where 'default' is not enumerated, e.g. NVIDIA boxes)
  4) the first device with output channels
This mirrors the patched SpeakerDevice, so the test follows the same output
as real experiments with no per-host configuration. Use --device-index /
--device-name to override for diagnostics (e.g. probing a raw hw: device).

Channel count defaults to stereo (2); override with PTB_MAX_OUT_CHANNELS so
128-channel ALSA PCMs don't cause a FillBuffer channel mismatch.

Exit code: always 0 (qualitative test).

Run:
  psychopy --direct test_ptb_single.py
  /opt/psychopy/PsychoPy-2026.1.3-Python3.10/.venv/bin/python3 test_ptb_single.py --verbose
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


def _device_fields(d):
    """Extract (idx, name, sr, outch) from a PTB device dict, or None if no index."""
    idx = d.get("DeviceIndex", d.get("deviceIndex", None))
    if idx is None:
        return None
    name = d.get("DeviceName", d.get("deviceName", "unknown"))
    sr = float(d.get("DefaultSampleRate", d.get("defaultSampleRate", 44100.0)))
    outch = int(float(d.get("NrOutputChannels", d.get("nrOutputChannels", 2)) or 2))
    return int(float(idx)), name, sr, outch


def _outch(d):
    return float(d.get("NrOutputChannels", d.get("nrOutputChannels", 0)) or 0)


def _dname(d):
    return d.get("DeviceName", d.get("deviceName", "")) or ""


def _auto_select(devices):
    """Policy-based auto selection, mirroring the patched SpeakerDevice:
      1) 'default'  2) 'sysdefault'  3) first analog hw: (non-HDMI/NVIDIA)
      4) first device with output channels.
    Returns the chosen device dict, or None.
    """
    outs = [d for d in devices if _outch(d) > 0]
    if not outs:
        return None
    for d in outs:
        if _dname(d) == "default":
            return d
    for d in outs:
        if _dname(d) == "sysdefault":
            return d
    for d in outs:
        n = _dname(d)
        if "Analog" in n and "HDMI" not in n and "NVidia" not in n and "NVIDIA" not in n:
            return d
    return outs[0]


def choose_output_device(devices, device_index_arg, device_name_arg):
    """
    Selection priority:
      1) --device-index (explicit numeric override, for diagnostics)
      2) --device-name  (explicit name override)
      3) auto by policy (see _auto_select): 'default' -> 'sysdefault' ->
         analog hw: -> first output device
    """
    if not devices:
        return None, None, None, None

    # 1) explicit index override
    if device_index_arg is not None:
        for d in devices:
            idx = d.get("DeviceIndex", d.get("deviceIndex", None))
            if idx is not None and int(float(idx)) == int(device_index_arg):
                return _device_fields(d)
        print(f"WARNING: --device-index {device_index_arg} not found; falling back to auto selection.")

    # 2) explicit name override
    if device_name_arg is not None:
        for d in devices:
            if _dname(d) == device_name_arg:
                return _device_fields(d)
        print(f"WARNING: --device-name '{device_name_arg}' not found; falling back to auto selection.")

    # 3) auto by policy
    chosen = _auto_select(devices)
    if chosen is not None:
        return _device_fields(chosen)

    return None, None, None, None


def clamp_channels(dev_outch):
    """
    Clamp output channels to stereo by default (mirrors the SpeakerDevice
    patch). Many ALSA 'default'/'sysdefault' PCMs advertise 128 channels,
    which mismatches stereo buffers (PTB FillBuffer error). Override with
    PTB_MAX_OUT_CHANNELS if a node genuinely needs more channels.
    """
    dev_out = int(dev_outch)
    max_out = int(os.environ.get("PTB_MAX_OUT_CHANNELS", 2))
    if max_out > 0:
        return max(1, min(dev_out, max_out))
    return max(1, dev_out)


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
    return y  # shape (N,)


def to_channels(samples_mono, channels: int):
    """
    PTB FillBuffer expects shape (numSamples, numChannels).
    Duplicate mono into N channels.
    """
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
    print(f"Single beep      : {flag(RESULTS.get('single_ok', False))}")


def main():
    ap = argparse.ArgumentParser(description="PTB audio-only diagnostic — single beep")
    ap.add_argument("--verbose", action="store_true", help="print verbose PTB device/config info")
    ap.add_argument("--device-index", type=int, default=None, help="PTB DeviceIndex to use (from GetDevices)")
    ap.add_argument("--device-name", type=str, default=None, help="PTB DeviceName to use (e.g. 'default')")
    ap.add_argument("--sr", type=int, default=0, help="sample rate override (0 = device default)")
    ap.add_argument("--latency-class", type=int, default=1, help="PTB latency class (default 1)")
    ap.add_argument("--fade-secs", type=float, default=0.01, help="fade in/out seconds (default 0.01)")
    ap.add_argument("--hz", type=float, default=440.0, help="beep frequency (default 440)")
    ap.add_argument("--secs", type=float, default=1.0, help="beep duration seconds (default 1.0)")
    args = ap.parse_args()

    env_info()
    devices = ptb_info(verbose=args.verbose)

    section("3) Device selection")
    dev_idx, dev_name, dev_sr, dev_outch = choose_output_device(
        devices, args.device_index, args.device_name
    )
    if dev_idx is None:
        print("ERROR: could not select an output device from PTB list.")
        print_summary()
        return 0

    sr = args.sr if args.sr and args.sr > 0 else int(dev_sr) if dev_sr else 44100
    channels = clamp_channels(dev_outch)  # match device out channels, clamped
    print(f"Selected device: idx={dev_idx}, name='{dev_name}', defaultSR={dev_sr}, outCh={dev_outch}")
    print(f"Using sample rate: {sr} Hz")
    print(f"Using channels   : {channels}")

    section("4) TEST: single beep")
    pahandle = None
    try:
        pahandle = open_ptb_stream(dev_idx, sr, channels=channels, latency_class=args.latency_class)
        RESULTS["stream_open_ok"] = True

        mono = make_tone(args.hz, args.secs, sr, args.fade_secs)
        buf = to_channels(mono, channels)
        RESULTS["single_ok"] = bool(play_buffer(pahandle, buf, args.secs, "Single beep"))

    except Exception as e:
        RESULTS["stream_open_ok"] = False
        RESULTS["single_ok"] = False
        print(f"PTB single test failed: {e}")

    finally:
        if pahandle is not None:
            close_ptb_stream(pahandle)

    print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())