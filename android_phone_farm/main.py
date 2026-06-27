import sys
import os
import logging
import shutil

from PyQt6.QtWidgets import QApplication, QMessageBox
try:
    import qdarktheme
except ImportError:
    qdarktheme = None

import config
from ui.main_window import MainWindow

# Redirect output for frozen environment (pyinstaller) to avoid Bad File Descriptor errors
if hasattr(sys, 'frozen'):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    log_handlers = [logging.FileHandler("phone_farm.log", encoding="utf-8")]
else:
    log_handlers = [logging.StreamHandler(sys.stdout)]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)

def check_dependencies():
    """
    Check if ADB and scrcpy binaries are available.
    Returns a list of warnings if missing.
    """
    adb_path = config.get_executable_path("adb")
    scrcpy_path = config.get_executable_path("scrcpy")
    
    warnings = []
    
    # Check ADB
    if adb_path == "adb" and not shutil.which("adb"):
        warnings.append("- ADB (Android Debug Bridge): Không tìm thấy trong PATH hoặc vị trí cài đặt mặc định.")
        
    # Check Scrcpy
    if scrcpy_path == "scrcpy" and not shutil.which("scrcpy"):
        warnings.append("- scrcpy: Không tìm thấy công cụ stream màn hình trong PATH hoặc vị trí cài đặt mặc định.")
        
    return warnings

def main():
    # 1. Initialize Qt Application
    app = QApplication(sys.argv)
    
    # pyqtdarktheme 2.1.0 chỉ khai báo hỗ trợ đến Python 3.11.
    # Trên Python 3.12+, app vẫn chạy với giao diện Qt mặc định.
    if qdarktheme:
        app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    else:
        logging.warning("Không có qdarktheme; dùng giao diện Qt mặc định.")
    
    # 2. Check environment dependencies before displaying main UI
    warnings = check_dependencies()
    if warnings:
        warn_msg = (
            "Phần mềm phát hiện một số công cụ phụ thuộc chưa được cài đặt:\n\n"
            + "\n".join(warnings) +
            "\n\nỨng dụng vẫn sẽ khởi chạy, tuy nhiên tính năng stream và điều khiển sẽ không hoạt động. "
            "Bạn có thể cấu hình lại đường dẫn trong file 'config.json' sau khi ứng dụng mở."
        )
        QMessageBox.warning(None, "Cảnh báo thiếu công cụ", warn_msg)

    # 3. Create and show MainWindow
    try:
        logging.info("Đang khởi động giao diện chính của ứng dụng...")
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f"Lỗi nghiêm trọng làm sập ứng dụng: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
