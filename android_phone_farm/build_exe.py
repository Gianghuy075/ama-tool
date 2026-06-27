import subprocess
import os
import sys

def build():
    spec_file = "main.spec"
    print(f"Starting build of {spec_file} using PyInstaller...")
    
    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    log_path = r"C:\Users\Admin\AppData\Local\Temp\pybuild_full.log"
    # Create temp directory if needed, or save inside workspace
    workspace_log_path = r"C:\Users\Admin\.gemini\antigravity\scratch\android_phone_farm\pybuild_full.log"
    
    with open(workspace_log_path, "w", encoding="utf-8") as f:
        f.write("=== STDOUT ===\n")
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)
        f.write(f"\nExit code: {result.returncode}\n")
        
    print(f"Build completed with exit code: {result.returncode}")
    print(f"Details written to pybuild_full.log")

if __name__ == "__main__":
    build()
