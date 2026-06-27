import subprocess
import time

print("Starting main.py...")
proc = subprocess.Popen(
    ["py", "main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print("Started PID:", proc.pid)
time.sleep(10.0) # Wait for 10 seconds to let it connect and log errors

print("Terminating main.py...")
proc.terminate()
try:
    stdout, stderr = proc.communicate(timeout=3)
except subprocess.TimeoutExpired:
    proc.kill()
    stdout, stderr = proc.communicate()

print("=== STDOUT ===")
print(stdout)
print("=== STDERR ===")
print(stderr)
