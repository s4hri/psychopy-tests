# psychopy-tests

This repository provides a set of qualitative audio and visual diagnostic scripts for PsychoPy and Psychtoolbox (PTB) environments. The tests are designed to verify basic audio/visual functionality, device configuration, and channel separation on a variety of hardware setups. All tests are intended for quick, human-verifiable checks and are CI-friendly (always exit code 0).

## Overview

Scripts in this repository allow you to:
- Run visual and audio sanity checks using PsychoPy (with keyboard input and color changes)
- Test single beep playback and device configuration using PTB
- Verify mixing and timing of overlapping tones
- Check stereo channel separation and crosstalk

## Dependencies

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (for visual/audio tests)
- [psychtoolbox](https://github.com/Psychtoolbox-3/Psychtoolbox-3) (for PTB tests)
- numpy


## Usage

All scripts are standalone and can be run directly with Python 3 with PsychoPy and/or Psychtoolbox installed.

Example commands:
```bash
/opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/bin/python3 test_psychopy.py
```
Or, if using a PsychoPy distribution:
```bash
psychopy --direct test_psychopy.py
psychopy --direct test_ptb_single.py
```

Some script supports command-line arguments for device selection, sample rate, tone frequency, duration, and verbosity. See the script headers for details.


## License

MIT License (see LICENSE file).