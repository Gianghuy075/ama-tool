import subprocess

adb_path = r"C:\Users\Admin\Downloads\BoxPhone\platform-tools\adb.exe"

# Get devices
res = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
print("Current devices:")
print(res.stdout)

for line in res.stdout.splitlines():
    if "offline" in line:
        serial = line.split()[0]
        print(f"Reconnecting {serial}...")
        sub_res = subprocess.run([adb_path, "-s", serial, "reconnect"], capture_output=True, text=True)
        print(sub_res.stdout.strip(), sub_res.stderr.strip())

res2 = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
print("After reconnect devices:")
print(res2.stdout)
