import os
path = r"C:\Users\Admin\.gemini\antigravity\scratch\android_phone_farm\test_write.txt"
try:
    with open(path, "w") as f:
        f.write("hello")
    print("Done writing successfully")
except Exception as e:
    print("Error writing:", e)
