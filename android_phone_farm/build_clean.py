import os
import shutil
import subprocess
import sys

def clean_and_build():
    # 1. Tắt các tiến trình đang chạy để tránh khóa file
    for proc_name in ["main.exe", "GDP-tool-phone.exe"]:
        try:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            pass
            
    cwd = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(cwd, "dist")
    build_dir = os.path.join(cwd, "build")
    
    # Xử lý thư mục build
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception:
            for i in range(100):
                old_path = f"{build_dir}_old_{i}"
                if not os.path.exists(old_path):
                    try:
                        os.rename(build_dir, old_path)
                        break
                    except Exception:
                        pass
                        
    # Xử lý thư mục dist
    if os.path.exists(dist_dir):
        # Duyệt qua các tệp tin trong dist và đổi tên nếu bị lock
        for root, dirs, files in os.walk(dist_dir, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except Exception:
                    # Đổi tên file bị lock để giải phóng đường dẫn
                    for i in range(100):
                        old_file_path = f"{file_path}_old_{i}"
                        if not os.path.exists(old_file_path):
                            try:
                                os.rename(file_path, old_file_path)
                                break
                            except Exception:
                                pass
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    shutil.rmtree(dir_path)
                except Exception:
                    pass
        try:
            shutil.rmtree(dist_dir)
        except Exception:
            pass

    # 3. Khởi chạy PyInstaller biên dịch lại
    cmd = [sys.executable, "-m", "PyInstaller", "main.spec", "--noconfirm"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Lưu log chi tiết
    log_path = os.path.join(cwd, "pybuild_final.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== STDOUT ===\n")
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)
        f.write(f"\nExit code: {result.returncode}\n")
        
    print("Build finished with exit code:", result.returncode)

if __name__ == "__main__":
    clean_and_build()
