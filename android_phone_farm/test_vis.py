import subprocess
import time
import ctypes

user32 = ctypes.windll.user32
proc = subprocess.Popen([
    r'C:\Users\Admin\Downloads\BoxPhone\scrcpy-win64-v4.0\scrcpy.exe', 
    '-s', 'R58M20FKSCW', 
    '--window-title', 'test_vis', 
    '--max-fps', '15', 
    '--video-bit-rate', '1M', 
    '--max-size', '480', 
    '--no-audio'
], creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

t0 = time.time()
while time.time() - t0 < 5.0:
    hwnd = user32.FindWindowW(None, 'test_vis')
    if hwnd:
        print('hwnd:', hwnd, 'visible:', user32.IsWindowVisible(hwnd))
    else:
        print('no window yet')
    time.sleep(0.5)

print("Terminating...")
proc.terminate()
proc.wait()
