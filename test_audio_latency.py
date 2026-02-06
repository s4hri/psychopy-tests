import ctypes
xlib = ctypes.cdll.LoadLibrary("libX11.so")
xlib.XInitThreads()

import socket
hostname = socket.gethostname()

import sys
from pathlib import Path
import csv
from datetime import datetime
import time

import psychopy
psychopy.prefs.hardware['audioLib'] = ['PTB']
psychopy.prefs.hardware['audioLatencyMode'] = 4

from psychopy import sound, core
from psychopy.hardware import keyboard

from psychtoolbox import PsychPortAudio

try:
    ptb_devices = PsychPortAudio("GetDevices")
except Exception as e:
    ptb_devices = []


device_info = []
for d in ptb_devices:
    idx = d.get("DeviceIndex", d.get("deviceIndex", ""))
    name = d.get("DeviceName", d.get("deviceName", ""))
    host = d.get("HostAudioAPIName", d.get("hostAudioAPIName", ""))
    outch = d.get("NrOutputChannels", d.get("nrOutputChannels", 0))
    device_info.append(f"{idx}:{name}:{host}:out{outch}")

selected_audio_device = psychopy.prefs.hardware.get("audioDevice", "unknown")


N_TRIALS = 51
OUT_DIR = Path("./csv")

sounds = {
    "A": sound.Sound('A', secs=0.2),
}

kb = keyboard.Keyboard()

for sound_name, mySound in sounds.items():
    out_csv = OUT_DIR / f"audio_latency_{sound_name}_{hostname}.csv"

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        w.writerow(["audio_device_selected", selected_audio_device])
        w.writerow(["ptb_devices"])
        for dev in device_info:
            w.writerow([dev])
        w.writerow([])
        w.writerow(["timestamp", "latency_ms"])

        # This list contains all values of latencies for a specific sound, used for mean
        latencies = []

        for i in range(N_TRIALS):
            kb.clearEvents()
            kb.clock.reset()
            mySound.play()

            k = kb.waitKeys(keyList=['5', 'escape'], waitRelease=False)[0]
            if k.name == 'escape':
                core.quit()

            if i == 0:
                mySound.stop()
                core.wait(1)
                continue

            ts = datetime.now().isoformat(timespec="microseconds")
            lat_ms = k.rt * 1000.0
            latencies.append(lat_ms)

            print(sound_name, lat_ms)
            w.writerow([ts, f"{lat_ms:.3f}"])

            mySound.stop()
            core.wait(1)

        mean_lat = sum(latencies) / len(latencies)
        w.writerow(["MEAN", f"{mean_lat:.3f}"])

core.quit()
