import os
import json
import shutil

# Đường dẫn lưu cấu hình cục bộ
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "scrcpy_path": "scrcpy",  # Mặc định gọi qua PATH
    "adb_path": "adb",        # Mặc định gọi qua PATH
    "bitrate": "300K",        # Cấu hình siêu nhẹ mới: 300K bitrate giảm cực mạnh tải USB
    "max_fps": 5,             # Cấu hình siêu nhẹ mới: 5 FPS tránh quá tải CPU & sụt áp
    "max_size": 320,          # Cấu hình siêu nhẹ mới: 320px độ phân giải dọc để giảm tải truyền tải
    "show_touches": False,    # Hiển thị điểm chạm trên thiết bị
    "stay_awake": False,      # Tắt mặc định để CPU điện thoại không bị giữ 100% liên tục
    "turn_screen_off": True,  # Tự động tắt màn hình vật lý điện thoại để giảm 70% điện năng tiêu thụ
    "card_width": 200         # Kích thước chiều rộng mặc định của card điện thoại
}

def load_config():
    """Tải cấu hình từ file JSON, nếu không có trả về mặc định."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                # Đảm bảo có đủ các key mặc định nếu file thiếu
                merged = DEFAULT_CONFIG.copy()
                merged.update(config_data)
                return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Lưu cấu hình hiện tại vào file JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception:
        return False

def get_executable_path(name):
    """
    Tìm kiếm đường dẫn thực thi của adb hoặc scrcpy.
    Ưu tiên: 
      1. Đường dẫn cấu hình trong file config.json (nếu tồn tại đường dẫn thực tế).
      2. Trong PATH hệ thống.
      3. Các thư mục cài đặt mặc định phổ biến trên Windows.
    """
    config = load_config()
    key = f"{name}_path"
    
    # 1. Kiểm tra cấu hình cụ thể
    if key in config and config[key] and config[key] != name:
        if os.path.exists(config[key]):
            return config[key]
            
    # 2. Tìm trong biến môi trường PATH
    path = shutil.which(name)
    if path:
        return path
        
    # 3. Tìm các vị trí phổ biến trên Windows
    if name == "adb":
        common_paths = [
            r"C:\Users\Admin\Downloads\BoxPhone\platform-tools\adb.exe",
            r"C:\platform-tools\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
            r"C:\Android\Sdk\platform-tools\adb.exe"
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
    elif name == "scrcpy":
        common_paths = [
            r"C:\Users\Admin\Downloads\BoxPhone\scrcpy-win64-v4.0\scrcpy.exe",
            r"C:\scrcpy\scrcpy.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\scrcpy\scrcpy.exe"),
            r"C:\Program Files\scrcpy\scrcpy.exe",
            r"C:\Program Files (x86)\scrcpy\scrcpy.exe"
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
                
    # Trả về tên mặc định nếu không tìm thấy để hệ thống thử gọi qua cmd
    return name
