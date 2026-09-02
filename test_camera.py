#!/usr/bin/env python3
"""
PsychoPy camera capture sanity test.

This example opens the first available camera, records a short clip, and saves
it as test_video.mp4.

Run:
  psychopy --direct test_camera.py
  /opt/psychopy/PsychoPy-2025.1.1-Python3.10/.venv/bin/python3 test_camera.py

Notes:
- This is a qualitative test intended to confirm the camera backend can open,
  record, and save a video without crashing.
- The default camera index and backend may require adjustment on different hosts.
"""

from psychopy.hardware.camera import Camera
from psychopy import core

cam = Camera(
    device=0,
    cameraLib="ffpyplayer",
    frameRate=30,
    frameSize=(640, 480)
)

print("Opening camera...")
cam.open()

print("Recording 5 seconds...")
cam.record()

clock = core.Clock()

while clock.getTime() < 5:
    cam.poll()
    core.wait(0.001)

print("Stopping...")
cam.stop()

print("Saving...")
cam.save("test_video.mp4", useThreads=False)

cam.close()

print("Done: test_video.mp4")
