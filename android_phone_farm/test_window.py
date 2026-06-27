import subprocess
import os
import ctypes
import time

user32 = ctypes.windll.user32

scrcpy_path = r"C:\Users\Admin\Downloads\BoxPhone\scrcpy-win64-v4.0\scrcpy.exe"
serial = "R58M20FKSCW"
window_title = f"scrcpy_farm_{serial}"

cmd = [
    scrcpy_path,
    "-s", serial,
    "--window-title", window_title,
    "--max-fps", "15",
    "--video-bit-rate", "1M",
    "--max-size", "480",
    "--no-audio"
]

print("Starting scrcpy...")
creationflags = 0x08000000
proc = subprocess.Popen(
    cmd,
    creationflags=creationflags,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

print("Started PID:", proc.pid)

start_time = time.time()
found = False
while time.time() - start_time < 8.0:
    hwnd = user32.FindWindowW(None, window_title)
    if hwnd:
        visible = user32.IsWindowVisible(hwnd)
        print(f"Found window HWND: {hwnd}, IsWindowVisible: {visible}")
        found = True
        break
    time.sleep(0.2)

if not found:
    print("Window not found within 8 seconds!")

print("Terminating process...")
proc.terminate()
proc.wait()
