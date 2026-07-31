#!/usr/bin/env python3
"""
PTB (Psychtoolbox) audio-only diagnostic — MIXED OVERLAP BUFFER

Plays one buffer containing overlap:
- D4 (~293.66 Hz) for 5 s (t=0)
- A4 (440 Hz) for 3 s starting at t=2 s

IMPORTANT: FillBuffer expects shape (numSamples, numChannels).

Device selection priority (first match wins):
  1) --device-index (explicit numeric override, for diagnostics)
  2) --device-name  (explicit selector: exact name or hw token)
  3) PSYCHOPY_AUDIO_DEVICE env var (per-host selector: exact name or hw token)
  4) auto: 'default' -> 'sysdefault' -> first device with output channels

The selector may be an exact PTB DeviceName (e.g. 'default') or an ALSA hw
token (e.g. 'hw:2,0'), which PortAudio embeds verbatim in raw-device names.
This mirrors the patched SpeakerDevice. PSYCHOPY_AUDIO_DEVICE is typically
set per host from `aplay -l` (see README).

Channel count is clamped by PTB_MAX_OUT_CHANNELS (if set), matching the
SpeakerDevice patch, so 128-channel ALSA PCMs open as stereo.

Run:
  psychopy --direct test_ptb_mixed.py
  /opt/psychopy/PsychoPy-2026.1.3-Python3.10/.venv/bin/python3 test_ptb_mixed.py --verbose

Exit code: always 0 (qualitative test).
"""

import argparse
import os
import sys
import time
import platform
from pprint import pformat

RESULTS = {}

# Preference order for automatic device selection (by DeviceName).
# 'default' routes through PulseAudio and follows the system-selected sink.
AUTO_NAME_PRIORITY = ("default", "sysdefault")


def section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def env_info():
    section("1) Runtime & environment")
    print(f"Python   : {platform.python_version()} ({sys.executable})")
    print(f"Platform : {platform.platform()}")
    print(f"User/UID : {os.getenv('USER', 'unknown')} / {os.getuid()}")
    for k in ["DISPLAY", "WAYLAND_DISPLAY", "PULSE_SERVER", "PIPEWIRE_REMOTE", "PSYCHOPY_AUDIO_DEVICE"]:
        v = os.environ.get(k)
        if v:
            print(f"{k:20}: {v}")


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


def _name_matches(profile_name, wanted):
    """True if a PTB DeviceName matches a selector.

    `wanted` may be an exact DeviceName ('default', 'sysdefault', or a full
    'HDA Intel PCH: ALC623 Analog (hw:2,0)') or an ALSA hw token ('hw:2,0' /
    '(hw:2,0)') which PortAudio embeds verbatim in raw-device names.
    """
    if not wanted:
        return False
    if profile_name == wanted:
        return True
    if wanted.startswith("hw:") and "({})".format(wanted) in profile_name:
        return True
    if wanted.startswith("(hw:") and wanted in profile_name:
        return True
    return False


def _find_by_selector(devices, selector):
    """Return _device_fields for the first output-capable device matching
    `selector` (exact name or hw token), or None."""
    for d in devices:
        name = d.get("DeviceName", d.get("deviceName", "")) or ""
        outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
        if _name_matches(name, selector) and outch and float(outch) > 0:
            return _device_fields(d)
    return None


def choose_output_device(devices, device_index_arg, device_name_arg):
    """
    Selection priority:
      1) --device-index (explicit numeric override, for diagnostics)
      2) --device-name, else PSYCHOPY_AUDIO_DEVICE env var
         (exact DeviceName or ALSA hw token, e.g. 'default' or 'hw:2,0')
      3) auto: first device whose DeviceName matches AUTO_NAME_PRIORITY,
         in order ('default' first) -> follows system-selected sink via Pulse
      4) fallback: first device with > 0 output channels
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

    # 2) explicit --device-name, else per-host PSYCHOPY_AUDIO_DEVICE env var
    selector = device_name_arg or os.environ.get("PSYCHOPY_AUDIO_DEVICE", "").strip() or None
    if selector:
        fields = _find_by_selector(devices, selector)
        if fields is not None:
            return fields
        print(f"WARNING: device selector '{selector}' not found; falling back to auto selection.")

    # 3) auto by name priority (prefer 'default' -> Pulse -> system sink)
    for wanted in AUTO_NAME_PRIORITY:
        for d in devices:
            name = d.get("DeviceName", d.get("deviceName", None))
            outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
            if name == wanted and outch and float(outch) > 0:
                return _device_fields(d)

    # 4) fallback: first device with output channels
    for d in devices:
        outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
        if outch and float(outch) > 0:
            fields = _device_fields(d)
            if fields is not None:
                return fields

    return None, None, None, None


def clamp_channels(dev_outch):
    """
    Clamp output channels by PTB_MAX_OUT_CHANNELS (if set), mirroring the
    SpeakerDevice patch. ALSA 'default'/'sysdefault' advertise 128 channels;
    with PTB_MAX_OUT_CHANNELS=2 this opens them as stereo.
    """
    dev_out = int(dev_outch)
    max_out = int(os.environ.get("PTB_MAX_OUT_CHANNELS", dev_out))
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
    ap.add_argument("--device-name", type=str, default=None,
                    help="PTB device selector: exact DeviceName (e.g. 'default') or hw token (e.g. 'hw:2,0')")
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
    dev_idx, dev_name, dev_sr, dev_outch = choose_output_device(
        devices, args.device_index, args.device_name
    )
    if dev_idx is None:
        print("ERROR: could not select an output device from PTB list.")
        print_summary()
        return 0

    sr = args.sr if args.sr and args.sr > 0 else int(dev_sr) if dev_sr else 44100
    channels = clamp_channels(dev_outch)
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