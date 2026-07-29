# psychopy-tests

This repository provides a set of qualitative audio and visual diagnostic scripts for PsychoPy and Psychtoolbox (PTB) environments. The tests are designed to verify basic audio/visual functionality, device configuration, and channel separation on a variety of hardware setups. All tests are intended for quick, human-verifiable checks and are CI-friendly (always exit code 0).

## Overview

Scripts in this repository allow you to:
- Run visual and audio sanity checks using PsychoPy (with keyboard input and color changes)
- Test single beep playback and device configuration using PTB
- Verify mixing and timing of overlapping tones
- Check stereo channel separation and crosstalk

## Scripts

- `test_psychopy.py` — end-to-end PsychoPy check: real-time scheduling/privileges, fullscreen visual, keyboard input, and a beep per trial.
- `test_ptb_single.py` — plays a single beep through one PTB output stream; prints the full device list and selected device.
- `test_ptb_mixed.py` — plays one buffer with two overlapping tones (a D tone, with an A tone starting partway through) to check mixing and timing.
- `test_ptb_stereo_mix.py` — verifies stereo left/right separation: left-only, then right-only, then both tones simultaneously in their own channels.

## Dependencies

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (for visual/audio tests)
- [psychtoolbox](https://github.com/Psychtoolbox-3/Psychtoolbox-3) (for PTB tests)
- numpy

## Usage

All scripts are standalone and can be run directly with Python 3 with PsychoPy and/or Psychtoolbox installed.

Run with the PsychoPy virtual environment's Python directly:
```bash
/opt/psychopy/PsychoPy-2026.1.3-Python3.10/.venv/bin/python3 test_psychopy.py
```

Or, using a PsychoPy distribution's launcher:
```bash
psychopy --direct test_psychopy.py
psychopy --direct test_ptb_single.py
```

Each script supports command-line arguments for device selection, sample rate, tone frequency, duration, and verbosity. Run a script with `--help`, or see the script header, for the full list.

## Audio device selection

The PTB test scripts (`test_ptb_single.py`, `test_ptb_mixed.py`, `test_ptb_stereo_mix.py`) select an output device using the following priority:

1. `--device-index N` — explicit numeric device index (from the printed device list). Use for diagnostics, e.g. probing a specific piece of hardware.
2. `--device-name NAME` — explicit device name, e.g. `--device-name default`.
3. Automatic: the first device named `default`, then `sysdefault`, then the first device reporting output channels.

The automatic default prefers the ALSA `default` PCM, which routes through PulseAudio and therefore follows whatever output is selected in the system sound settings. This avoids accidentally binding to a raw hardware device (for example a USB dock) that bypasses PulseAudio and ignores the system-selected output. Note that device indices are not stable — they can change when hardware is plugged in or removed — so selecting by name (or letting the automatic policy pick `default`) is more robust than pinning an index.

To list available devices without playing anything:
```bash
psychopy --direct test_ptb_stereo_mix.py --list-devices
```

## Channel count (PTB_MAX_OUT_CHANNELS)

Some ALSA PCMs (notably `default` and `sysdefault`) advertise a large maximum channel count (e.g. 128). Opening a PTB stream at that width and then supplying stereo audio causes a `FillBuffer` channel-count mismatch. To avoid this, set the `PTB_MAX_OUT_CHANNELS` environment variable to clamp the number of output channels:

```bash
export PTB_MAX_OUT_CHANNELS=2
```

When set, the PTB test scripts (and a correspondingly patched PsychoPy `SpeakerDevice`) open the stream with at most this many channels. When unset, the device-reported channel count is used unchanged, so genuine multichannel devices are unaffected.

## Troubleshooting

- **`Number of columns of audio data matrix doesn't match number of output channels`** — the stream opened with more channels than the audio buffer has. Set `PTB_MAX_OUT_CHANNELS=2` (see above).
- **Audio plays on the wrong output** (e.g. a dock instead of the system-selected speaker) — the selected device is bypassing PulseAudio. Use `--device-name default`, or rely on the automatic selection, so playback follows the system sound settings.
- **No sound at all** — confirm PulseAudio is reachable (`pactl info`) and that the `default` device is listed by the script's device dump.

## License

MIT License (see LICENSE file).