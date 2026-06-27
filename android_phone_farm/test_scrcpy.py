import subprocess
import os

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

print("Running command:", " ".join(cmd))
try:
    creationflags = 0x08000000
    proc = subprocess.Popen(
        cmd,
        creationflags=creationflags,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("Started process with PID:", proc.pid)
    try:
        stdout, stderr = proc.communicate(timeout=3)
        print("Stdout:", stdout)
        print("Stderr:", stderr)
    except subprocess.TimeoutExpired:
        print("Process is still running after 3 seconds.")
        proc.terminate()
        stdout, stderr = proc.communicate()
        print("Stdout (on terminate):", stdout)
        print("Stderr (on terminate):", stderr)
except Exception as e:
    print("Failed to run subprocess:", e)
