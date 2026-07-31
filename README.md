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

Device selection is automatic and requires no configuration. The PTB test scripts (`test_ptb_single.py`, `test_ptb_mixed.py`, `test_ptb_stereo_mix.py`) and the patched PsychoPy `SpeakerDevice` select an output device by the same policy, in priority order:

1. A device named `default` — the ALSA `default` PCM, which routes through PulseAudio/PipeWire and follows the system-selected sink. Present on most machines where PortAudio enumerates the ALSA `default` PCM.
2. A device named `sysdefault`.
3. The first analog hardware output, excluding HDMI/NVIDIA devices — the real onboard output on machines where `default` is not enumerated by PortAudio (for example NVIDIA workstations where an HDMI audio card takes card 0).
4. The first device reporting output channels.

This policy is intentionally the same in the library and the test scripts, so the tests follow the same output as real experiments. It is designed to pick the correct output on machines with different audio stacks and card ordering **without any per-host configuration** — an identical image/container works across nodes.

For diagnostics, the test scripts accept explicit overrides:
- `--device-index N` — force a specific numeric device index (from the printed device list).
- `--device-name NAME` — force a specific device name, e.g. `--device-name default`.

Note that device indices are not stable — they can change when hardware is added or removed — so the automatic policy (or `--device-name`) is more robust than pinning an index.

To list available devices without playing anything:
```bash
psychopy --direct test_ptb_stereo_mix.py --list-devices
```

### Why the policy prefers `default` and excludes HDMI

The ALSA `default` device routes through the sound server and follows the output chosen in the system sound settings, so it is preferred where available. Raw hardware devices (a USB dock, an HDMI port with nothing connected) can appear first in enumeration and bypass the sound server; the policy avoids them by preferring `default`/`sysdefault` and, when falling back to hardware, skipping HDMI/NVIDIA outputs in favour of the analog output. Where `default` is not enumerated (some PipeWire configurations, or machines where an NVIDIA HDMI card occupies card 0), the policy lands on the analog hardware output instead — which reaches the same physical speakers, though it does not follow the system-settings sink.

## Channel count

Some ALSA PCMs (notably `default` and `sysdefault`) advertise a large maximum channel count (e.g. 128). Opening a PTB stream at that width and then supplying stereo audio causes a `FillBuffer` channel-count mismatch. To avoid this, the scripts and the patched `SpeakerDevice` clamp the output to **stereo (2 channels) by default**, with no configuration needed.

If a node genuinely needs more output channels, set the `PTB_MAX_OUT_CHANNELS` environment variable to raise the cap:

```bash
export PTB_MAX_OUT_CHANNELS=8
```

When unset, the effective cap is 2 (stereo). A value of `0` disables clamping and uses the device-reported channel count unchanged.

## Troubleshooting

- **`Number of columns of audio data matrix doesn't match number of output channels`** — the stream opened with more channels than the audio buffer has. This is handled by default (output is clamped to stereo); if you have raised `PTB_MAX_OUT_CHANNELS`, lower it back to `2`.
- **Audio plays on the wrong output** (e.g. an HDMI port or dock instead of the expected speaker) — the automatic policy normally avoids this by preferring `default` and skipping HDMI/NVIDIA. Use `--device-name` or `--device-index` to force a specific device, and `--list-devices` to see what PTB enumerates.
- **No sound at all** — confirm the sound server is reachable (`pactl info`) and inspect the script's device dump. On machines where PTB lists only raw `hw:` devices (no `default`), check `aplay -l` / `cat /proc/asound/cards` to see which card is the analog output; the policy targets the first analog, non-HDMI device.

## License

MIT License (see LICENSE file).