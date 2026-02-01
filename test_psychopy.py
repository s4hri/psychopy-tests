#!/usr/bin/env python3
"""
PsychoPy qualitative A/V + keyboard sanity test (5 trials)

Behavior (visual mode):
- Opens a fullscreen GREY background window with a text prompt.
- For each trial (default 5):
  - Shows: "Press any key to proceed (trial i/5)" in WHITE
  - Waits for a key press (ESC quits)
  - Plays ONE beep lasting `--beep-secs` (default 1.0s)
  - While the beep plays, the TEXT color changes (one color per trial)
  - When the beep ends, the text returns to WHITE
- Prints a simple summary at the end.
- Exits code 0 even on failures (CI-friendly qualitative test).

Audio-only mode:
- Runs the same trials in the terminal (press ENTER each trial), plays the beep.

Notes:
- Designed to be qualitative and generic across hardware/configurations.
- Avoids quantitative timing/FPS reports.

Run:
  psychopy --direct test_psychopy.py
  /opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/bin/python3 test_psychopy.py --audio-only
"""

import argparse
import os
import sys
import time
from contextlib import contextmanager

RESULTS = {}


def section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


@contextmanager
def psychopy_console_log_level(level_name: str):
    """Temporarily set PsychoPy console logging level (e.g., ERROR/CRITICAL)."""
    try:
        from psychopy import logging as psycholog
        prev = psycholog.console.level
        level = getattr(psycholog, level_name.upper(), psycholog.ERROR)
        psycholog.console.setLevel(level)
        yield
        psycholog.console.setLevel(prev)
    except Exception:
        yield


def test_python_caps():
    section("1) Python runtime and privileges")
    import platform

    print(f"Python   : {platform.python_version()}  ({sys.executable})")
    print(f"User/UID : {os.getenv('USER', 'unknown')} / {os.getuid()}")

    # nice
    try:
        cur = os.nice(0)
        print(f"nice() before: {cur}")
        os.nice(-20)
        after = os.nice(0)
        print(f"nice() after : {after}")
        RESULTS["nice_raise_ok"] = after < cur
    except Exception as e:
        print(f"nice() raise not available: {e}")
        RESULTS["nice_raise_ok"] = False

    # rlimits
    try:
        import resource
        rtprio = resource.getrlimit(resource.RLIMIT_RTPRIO)
        memlock = resource.getrlimit(resource.RLIMIT_MEMLOCK)
        print(f"RLIMIT_RTPRIO : {rtprio}")
        print(f"RLIMIT_MEMLOCK: {memlock}")
        RESULTS["rtprio_limit"] = rtprio
        RESULTS["memlock_limit"] = memlock
    except Exception as e:
        print(f"Could not read rlimits: {e}")

    # Try SCHED_FIFO briefly
    try:
        param = os.sched_param(10)
        os.sched_setscheduler(0, os.SCHED_FIFO, param)
        print("SCHED_FIFO(10) set successfully.")
        RESULTS["sched_fifo_ok"] = True
    except Exception as e:
        print(f"SCHED_FIFO not available/denied: {e}")
        RESULTS["sched_fifo_ok"] = False
    finally:
        try:
            os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
        except Exception:
            pass


def _have_gui_env() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _audio_tone_factory(freq_hz: float, beep_secs: float):
    """Create a PsychoPy tone if possible. Returns (tone, core) or (None, None)."""
    try:
        from psychopy import sound, core
        tone = sound.Sound(value=freq_hz, secs=beep_secs)
        return tone, core
    except Exception as e:
        print(f"Audio init failed: {e}")
        return None, None


def test_psychopy_trials_beep_text_color(
    quiet: bool,
    trials: int,
    tone_hz: float,
    beep_secs: float,
    grey_level: float,
    text_height: float,
):
    section("2) PsychoPy – key → 1s beep while TEXT changes color (trials)")

    if not _have_gui_env():
        print("No DISPLAY/WAYLAND_DISPLAY detected; skipping visual test.")
        RESULTS["visual_skipped"] = True
        return

    log_level = "CRITICAL" if quiet else "ERROR"

    # Trial colors for the TEXT (RGB in -1..1). One per trial; cycles if trials > len(colors).
    colors = [
        (1, -1, -1),   # red
        (-1, 1, -1),   # green
        (-1, -1, 1),   # blue
        (1, 1, -1),    # yellow
        (1, -1, 1),    # magenta
    ]

    key_presses = 0

    try:
        with psychopy_console_log_level(log_level):
            import psychopy
            from psychopy import visual, event

            print(f"PsychoPy: {psychopy.__version__}")

            # Audio init
            tone, core = _audio_tone_factory(tone_hz, beep_secs)
            RESULTS["audio_ok"] = tone is not None

            # Fullscreen window; GREY background stays constant.
            grey = (grey_level, grey_level, grey_level)

            win = visual.Window(
                fullscr=True,
                screen=0,
                allowGUI=False,
                units="pix",
                waitBlanking=True,
                checkTiming=False,
                color=grey,
                colorSpace="rgb",
            )
            RESULTS["visual_ok"] = True
            print(f"Window opened fullscreen: {win.size[0]}x{win.size[1]}")
            print("Press any key to proceed through trials. Press ESC to quit.")

            text = visual.TextStim(
                win,
                text="",
                color="white",      # default prompt color
                colorSpace="rgb",
                height=text_height,
                wrapWidth=win.size[0] * 0.9,
            )

            win.flip()

            for i in range(trials):
                trial_n = i + 1
                trial_color = colors[i % len(colors)]

                # Prompt in white
                text.color = (1, 1, 1)
                text.text = f"Press any key to proceed\n\nTrial {trial_n}/{trials}\n\n(ESC to quit)"
                text.draw()
                win.flip()

                keys = event.waitKeys()
                if not keys:
                    continue
                if "escape" in keys:
                    print("ESC pressed: exiting early.")
                    RESULTS["keyboard_ok"] = True
                    break

                key_presses += 1
                RESULTS["keyboard_ok"] = True

                # Change TEXT color + play beep for beep_secs
                text.color = trial_color
                text.text = f"BEEP\n\nTrial {trial_n}/{trials}"
                text.draw()
                win.flip()

                if tone is not None and core is not None:
                    tone.play()
                    core.wait(beep_secs)
                else:
                    time.sleep(beep_secs)

                # Return to white prompt text
                text.color = (1, 1, 1)
                text.text = "OK\n\nPress any key for next trial\n(ESC to quit)"
                text.draw()
                win.flip()

            win.close()

        RESULTS["trials_completed"] = key_presses
        print(f"Trials completed (non-ESC keypresses): {key_presses}/{trials}")

    except Exception as e:
        print(f"Visual/audio test failed: {e}")
        RESULTS["visual_ok"] = False
        RESULTS["keyboard_ok"] = False


def test_audio_only_terminal(trials: int, tone_hz: float, beep_secs: float):
    section("2) PsychoPy – audio-only terminal trials")
    print("Terminal mode: press ENTER to proceed each trial (Ctrl+C to abort).")

    try:
        import psychopy
        print(f"PsychoPy: {psychopy.__version__}")

        tone, core = _audio_tone_factory(tone_hz, beep_secs)
        RESULTS["audio_ok"] = tone is not None

        completed = 0
        for i in range(trials):
            trial_n = i + 1
            input(f"Press ENTER to proceed (trial {trial_n}/{trials})... ")
            completed += 1

            if tone is not None and core is not None:
                tone.play()
                core.wait(beep_secs)
            else:
                time.sleep(beep_secs)

        RESULTS["trials_completed"] = completed
        RESULTS["keyboard_ok"] = True

    except KeyboardInterrupt:
        print("Aborted by user.")
    except Exception as e:
        print(f"Audio-only test failed: {e}")
        RESULTS["audio_ok"] = False


def print_summary():
    section("SUMMARY")

    def flag(ok): return "OK" if ok else "FAIL"

    print(f"nice raise         : {flag(RESULTS.get('nice_raise_ok', False))}")
    print(f"SCHED_FIFO avail   : {flag(RESULTS.get('sched_fifo_ok', False))}")

    rl = RESULTS.get("rtprio_limit")
    ml = RESULTS.get("memlock_limit")
    if rl:
        print(f"RLIMIT_RTPRIO      : {rl}")
    if ml:
        print(f"RLIMIT_MEMLOCK     : {ml}")

    print(f"Audio init         : {flag(RESULTS.get('audio_ok', False))}")

    if RESULTS.get("visual_skipped"):
        print("Visual fullscreen  : SKIPPED (no DISPLAY/WAYLAND)")
    else:
        print(f"Visual fullscreen  : {flag(RESULTS.get('visual_ok', False))}")
        print(f"Keyboard input     : {flag(RESULTS.get('keyboard_ok', False))}")

    if "trials_completed" in RESULTS:
        print(f"Trials completed   : {RESULTS.get('trials_completed')}")


def main():
    ap = argparse.ArgumentParser(description="PsychoPy qualitative A/V + keyboard sanity test")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--audio-only", action="store_true", help="terminal-only audio trials (no window)")
    g.add_argument("--visual-only", action="store_true", help="fullscreen visual+keyboard trials (default)")
    ap.add_argument("--quiet", action="store_true", help="suppress most PsychoPy warning spam")
    ap.add_argument("--trials", type=int, default=5, help="number of trials (default: 5)")
    ap.add_argument("--tone-hz", type=float, default=440.0, help="tone frequency Hz (default: 440)")
    ap.add_argument("--beep-secs", type=float, default=1.0, help="beep duration seconds (default: 1.0)")
    ap.add_argument(
        "--grey-level",
        type=float,
        default=0.0,
        help="grey background level in PsychoPy rgb (-1..1). Default 0.0 (mid-grey).",
    )
    ap.add_argument("--text-height", type=float, default=48.0, help="text height in pixels (default: 48)")
    args = ap.parse_args()

    test_python_caps()

    if args.audio_only:
        test_audio_only_terminal(
            trials=args.trials,
            tone_hz=args.tone_hz,
            beep_secs=args.beep_secs,
        )
    else:
        test_psychopy_trials_beep_text_color(
            quiet=args.quiet,
            trials=args.trials,
            tone_hz=args.tone_hz,
            beep_secs=args.beep_secs,
            grey_level=args.grey_level,
            text_height=args.text_height,
        )

    print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
