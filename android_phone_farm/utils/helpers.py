import ctypes
import time
from ctypes import wintypes

# Nạp thư viện user32.dll để gọi Windows API trực tiếp
user32 = ctypes.windll.user32

# Các hằng số Windows API cần thiết
GWL_STYLE = -16
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_THICKFRAME = 0x00040000
WS_CAPTION = WS_BORDER | WS_DLGFRAME

SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

def find_window_by_title(title: str, timeout: float = 15.0) -> int:
    """
    Tìm handle cửa sổ (HWND) theo tiêu đề của nó với cơ chế thử lại (timeout).
    Khi tìm thấy HWND, chờ thêm tối đa 5 giây để cửa sổ trở nên visible.
    Trả về HWND (int) nếu tìm thấy, ngược lại là None.
    """
    start_time = time.time()
    hwnd = None
    
    # Giai đoạn 1: Tìm HWND theo tiêu đề (chạy ít nhất 1 lần)
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        while time.time() - start_time < timeout:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                break
            time.sleep(0.2)
    
    if not hwnd:
        return None
        
    # Nếu timeout = 0.0, trả về ngay lập tức dựa trên trạng thái hiển thị
    if timeout == 0.0:
        if user32.IsWindowVisible(hwnd):
            return hwnd
        return None
    
    # Giai đoạn 2: Đợi cửa sổ trở nên visible (tối đa 5 giây thêm)
    vis_start = time.time()
    while time.time() - vis_start < 5.0:
        if user32.IsWindowVisible(hwnd):
            return hwnd
        time.sleep(0.2)
    
    # Trả về HWND dù chưa visible - vẫn có thể nhúng được
    return hwnd

def remove_window_borders(hwnd: int):
    """
    Xóa bỏ thanh tiêu đề (Caption) và viền của cửa sổ để khi nhúng vào GUI 
    trông như một widget tích hợp sẵn.
    """
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    
    # Loại bỏ Caption (thanh tiêu đề) và ThickFrame (viền kéo giãn)
    style &= ~WS_CAPTION
    style &= ~WS_THICKFRAME
    
    # Thêm cờ CHILD để biến nó thành cửa sổ con chính thức
    style |= WS_CHILD
    
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    
    # Cập nhật lại cấu trúc cửa sổ để áp dụng thay đổi style (SWP_FRAMECHANGED)
    user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0, 
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_FRAMECHANGED
    )

def embed_window(child_hwnd: int, parent_hwnd: int):
    """
    Nhúng cửa sổ con (child_hwnd) vào cửa sổ cha (parent_hwnd).
    """
    # 1. Loại bỏ các viền ngoài của cửa sổ scrcpy
    remove_window_borders(child_hwnd)
    
    # 2. Thay đổi cửa sổ cha của scrcpy thành Tkinter Frame
    user32.SetParent(child_hwnd, parent_hwnd)
    
    # 3. Hiển thị lại cửa sổ
    user32.SetWindowPos(child_hwnd, 0, 0, 0, 0, 0, SWP_SHOWWINDOW | SWP_NOMOVE | SWP_NOSIZE)

def resize_embed_window(child_hwnd: int, width: int, height: int):
    """
    Thay đổi kích thước cửa sổ con để lấp đầy không gian cửa sổ cha và đảm bảo hiển thị.
    """
    if child_hwnd:
        # MoveWindow(hwnd, x, y, width, height, repaint)
        user32.MoveWindow(child_hwnd, 0, 0, width, height, True)
        # Ép cửa sổ hiển thị và làm mới cấu trúc viền/vẽ lại để tránh màn hình đen
        user32.SetWindowPos(
            child_hwnd, 0, 0, 0, width, height,
            0x0040 | 0x0020  # SWP_SHOWWINDOW | SWP_FRAMECHANGED
        )

# Định nghĩa các kiểu dữ liệu đối số và giá trị trả về cho Windows API chéo process
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND

user32.SetActiveWindow.argtypes = [wintypes.HWND]
user32.SetActiveWindow.restype = wintypes.HWND

# Khai báo EnumWindows để duyệt cửa sổ theo PID
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

def find_window_by_pid(pid: int, timeout: float = 15.0) -> int:
    """
    Tìm handle cửa sổ (HWND) visible đầu tiên thuộc về tiến trình (PID) cụ thể với cơ chế thử lại.
    """
    if not pid:
        return None
        
    hwnd_found = [None]
    
    def enum_windows_callback(hwnd, lparam):
        win_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
        if win_pid.value == pid:
            if user32.IsWindowVisible(hwnd):
                hwnd_found[0] = hwnd
                return False  # Dừng duyệt
        return True  # Tiếp tục duyệt
        
    callback = WNDENUMPROC(enum_windows_callback)
    
    # Thực hiện duyệt lần đầu tiên trước khi vào vòng lặp timeout
    user32.EnumWindows(callback, 0)
    if hwnd_found[0]:
        return hwnd_found[0]
        
    start_time = time.time()
    while time.time() - start_time < timeout:
        user32.EnumWindows(callback, 0)
        if hwnd_found[0]:
            return hwnd_found[0]
        time.sleep(0.2)
        
    return None

def focus_window_cross_process(hwnd: int):
    """
    Chuyển focus bàn phím Windows sang cửa sổ con chéo process (scrcpy) một cách an toàn
    bằng cách liên kết hàng đợi tin nhắn của luồng hiện tại và luồng của cửa sổ đích.
    """
    if not hwnd:
        return
    try:
        # Lấy ID luồng của cửa sổ đích scrcpy
        win_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        # Lấy ID luồng hiện tại của ứng dụng Python/Tkinter
        curr_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        
        if win_thread_id != curr_thread_id:
            # Liên kết hàng đợi tin nhắn của 2 luồng
            user32.AttachThreadInput(curr_thread_id, win_thread_id, True)
            user32.SetFocus(hwnd)
            user32.SetActiveWindow(hwnd)
            # Ngắt liên kết sau khi đã hoàn thành set focus
            user32.AttachThreadInput(curr_thread_id, win_thread_id, False)
        else:
            user32.SetFocus(hwnd)
            user32.SetActiveWindow(hwnd)
    except Exception as e:
        import logging
        logging.error(f"Lỗi chuyển đổi focus chéo process: {e}")

