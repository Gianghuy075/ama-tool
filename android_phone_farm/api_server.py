from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import socket
import os
from typing import List, Union, Optional
import uvicorn
from utils import db_manager as db

app = FastAPI(title="GDP-tool-phone REST API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global reference to PyQt6 MainWindow GUI
main_window = None

# Pydantic models for request bodies
class TargetPayload(BaseModel):
    serial: Optional[str] = None
    serials: Optional[Union[str, List[str]]] = None

class TapPayload(TargetPayload):
    x: Optional[int] = None
    y: Optional[int] = None
    x_pct: Optional[float] = None
    y_pct: Optional[float] = None

class SwipePayload(TargetPayload):
    x1: Optional[int] = None
    y1: Optional[int] = None
    x2: Optional[int] = None
    y2: Optional[int] = None
    x1_pct: Optional[float] = None
    y1_pct: Optional[float] = None
    x2_pct: Optional[float] = None
    y2_pct: Optional[float] = None
    duration: Optional[int] = 300

class TextPayload(TargetPayload):
    text: str

class KeyEventPayload(TargetPayload):
    keycode: int

class ProxyRotatePayload(BaseModel):
    serial: str

class StreamPayload(BaseModel):
    serial: str
    action: str

class AdbCommandPayload(TargetPayload):
    command: str

class ScreenshotPayload(BaseModel):
    serial: str
    save_path: Optional[str] = Field(default=None, alias="savePath")

    class Config:
        populate_by_name = True

# New models for no-proxy experiment
class ClearCachePayload(BaseModel):
    serial: str
    package: str

class OpenAppPayload(BaseModel):
    serial: str
    package: str

class TypeCharPayload(BaseModel):
    serial: str
    char: str

class DeviceClickPayload(BaseModel):
    serial: str
    x: int
    y: int



def _get_target_serials(payload: TargetPayload) -> List[str]:
    """Helper to extract active target serials from request payload.
    Sử dụng device_cache thay vì gọi get_connected_devices() để tránh chạy subprocess adb devices mỗi request."""
    targets = []
    if payload.serial:
        targets.append(payload.serial)
    if payload.serials:
        if payload.serials == "all" and main_window:
            # Dùng device_cache keys thay vì chạy adb devices subprocess
            targets.extend(list(main_window.adb_handler.device_cache.keys()))
        elif isinstance(payload.serials, list):
            targets.extend(payload.serials)
            
    # De-duplicate and filter only devices present in cache (đã online từ lần scan gần nhất)
    if main_window:
        online_devices = set(main_window.adb_handler.device_cache.keys())
        targets = [t for t in list(set(targets)) if t in online_devices]
        
    return targets


@app.get("/api/devices")
def get_devices():
    """Get list of connected devices with detailed stream/master/selection status.
    Sử dụng device_cache + cached resolutions thay vì gọi ADB shell cho mỗi device."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống GUI chưa sẵn sàng")
        
    # Dùng device_cache keys thay vì chạy adb devices subprocess mỗi lần poll
    devices = list(main_window.adb_handler.device_cache.keys())
    active_streams = main_window.grid_view.get_active_streams()
    selected_devices = main_window.grid_view.get_selected_devices()
    
    result = []
    for d in devices:
        # get_device_resolution đã có cache nội bộ, không gọi shell lại nếu đã lấy trước đó
        w, h = main_window.adb_handler.get_device_resolution(d)
        result.append({
            "serial": d,
            "resolution": f"{w}x{h}",
            "is_streaming": d in active_streams,
            "is_master": False,
            "is_selected": d in selected_devices
        })
    return result


@app.post("/api/tap")
def tap_device(payload: TapPayload):
    """Simulate Tap/Click action on targets."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    targets = _get_target_serials(payload)
    if not targets:
        raise HTTPException(status_code=400, detail="Không tìm thấy thiết bị mục tiêu hợp lệ")
        
    if payload.x is None and payload.x_pct is None:
        raise HTTPException(status_code=400, detail="Thiếu thông tin tọa độ X hoặc X_pct")
    if payload.y is None and payload.y_pct is None:
        raise HTTPException(status_code=400, detail="Thiếu thông tin tọa độ Y hoặc Y_pct")
        
    for s in targets:
        if payload.x_pct is not None and payload.y_pct is not None:
            w, h = main_window.adb_handler.get_device_resolution(s)
            target_x = int(payload.x_pct * w)
            target_y = int(payload.y_pct * h)
        else:
            target_x = int(payload.x)
            target_y = int(payload.y)
            
        main_window.adb_handler.tap(s, target_x, target_y)
        
    return {"status": "success", "message": f"Đã gửi lệnh Tap tới {len(targets)} thiết bị"}


@app.post("/api/swipe")
def swipe_device(payload: SwipePayload):
    """Simulate Swipe action on targets."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    targets = _get_target_serials(payload)
    if not targets:
        raise HTTPException(status_code=400, detail="Không tìm thấy thiết bị mục tiêu hợp lệ")
        
    for s in targets:
        w, h = main_window.adb_handler.get_device_resolution(s)
        
        tx1 = int(payload.x1_pct * w) if payload.x1_pct is not None else int(payload.x1)
        ty1 = int(payload.y1_pct * h) if payload.y1_pct is not None else int(payload.y1)
        tx2 = int(payload.x2_pct * w) if payload.x2_pct is not None else int(payload.x2)
        ty2 = int(payload.y2_pct * h) if payload.y2_pct is not None else int(payload.y2)
        
        main_window.adb_handler.swipe(s, tx1, ty1, tx2, ty2, payload.duration)
        
    return {"status": "success", "message": f"Đã gửi lệnh Swipe tới {len(targets)} thiết bị"}


@app.post("/api/text")
def input_text(payload: TextPayload):
    """Type text on targets."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    targets = _get_target_serials(payload)
    if not targets:
        raise HTTPException(status_code=400, detail="Không tìm thấy thiết bị mục tiêu hợp lệ")
        
    for s in targets:
        main_window.adb_handler.input_text(s, payload.text)
        
    return {"status": "success", "message": f"Đã gửi văn bản nhập tới {len(targets)} thiết bị"}


@app.post("/api/keyevent")
def keyevent_device(payload: KeyEventPayload):
    """Simulate physical button press (Keyevent)."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    targets = _get_target_serials(payload)
    if not targets:
        raise HTTPException(status_code=400, detail="Không tìm thấy thiết bị mục tiêu hợp lệ")
        
    for s in targets:
        main_window.adb_handler.press_key(s, payload.keycode)
        
    return {"status": "success", "message": f"Đã gửi Keyevent {payload.keycode} tới {len(targets)} thiết bị"}


@app.get("/api/proxy")
def get_device_proxy(serial: str):
    """Get the current assigned proxy config for a device."""
    proxy = db.get_assigned_proxy(serial)
    if not proxy:
        return {"serial": serial, "has_proxy": False, "proxy": None}
        
    return {
        "serial": serial,
        "has_proxy": True,
        "proxy": proxy["proxy_str"],
        "ip": proxy["ip"],
        "port": proxy["port"],
        "username": proxy["username"],
        "password": proxy["password"],
        "status": proxy["status"]
    }


@app.post("/api/proxy/rotate")
def rotate_device_proxy(payload: ProxyRotatePayload):
    """Force rotate/change proxy IP for a specific device."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    success = main_window.rotate_device_ip(payload.serial, force_api_call=True)
    if success:
        return {"status": "success", "message": f"Đã xoay IP cho thiết bị {payload.serial}"}
    else:
        raise HTTPException(status_code=500, detail=f"Không thể xoay IP cho thiết bị {payload.serial} hoặc không có proxy rảnh")


@app.get("/api/data_usage")
def get_data_usages():
    """Get cumulative network data usage for all devices."""
    usages = db.get_all_data_usages()
    result = []
    for u in usages:
        result.append({
            "serial": u["phone_id"],
            "total_bytes_used": u["total_bytes_used"],
            "total_mb_used": round(u["total_bytes_used"] / (1024 * 1024), 2),
            "quota_limit_bytes": u["quota_limit_bytes"],
            "quota_limit_mb": round(u["quota_limit_bytes"] / (1024 * 1024), 2),
            "is_blocked": u["is_blocked"] == 1
        })
    return result


@app.post("/api/stream")
def toggle_stream_via_api(payload: StreamPayload):
    """Control stream scrcpy start/stop remotely."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    if payload.action not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="Tham số action phải là 'start' hoặc 'stop'")
        
    card = main_window.grid_view.cards.get(payload.serial)
    if not card:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị đang hoạt động với serial {payload.serial}")
        
    if payload.action == "start":
        main_window.stream_action_signal.emit(payload.serial, True)
    else:
        main_window.stream_action_signal.emit(payload.serial, False)
        
    return {"status": "success", "message": f"Đã gửi lệnh {payload.action} stream tới {payload.serial}"}


@app.post("/api/adb")
def run_adb_command(payload: AdbCommandPayload):
    """Run a raw adb shell command on targets."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    targets = _get_target_serials(payload)
    if not targets:
        raise HTTPException(status_code=400, detail="Không tìm thấy thiết bị mục tiêu hợp lệ")
        
    result = {}
    for s in targets:
        device = main_window.adb_handler.device_cache.get(s)
        if device:
            try:
                output = device.shell(payload.command)
                result[s] = {"success": True, "output": output}
            except Exception as e:
                result[s] = {"success": False, "output": str(e)}
        else:
            result[s] = {"success": False, "output": "Device not found"}
            
    response_data = {}
    if len(targets) == 1:
        single_target = targets[0]
        if result[single_target]["success"]:
            response_data = result[single_target]["output"]
        else:
            response_data = None
    else:
        response_data = result
        
    return {
        "code": 10000,
        "message": "SUCCESS",
        "data": response_data
    }


@app.post("/api/screenshot")
def take_screenshot(payload: ScreenshotPayload):
    """Take a screenshot of a device and optionally save it to a path."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
        
    device = main_window.adb_handler.device_cache.get(payload.serial)
    if not device:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị {payload.serial}")
        
    try:
        result_bytes = device.screencap()
        if payload.save_path:
            save_path = payload.save_path
            if os.path.isdir(save_path):
                file_path = os.path.join(save_path, f"{payload.serial}.png")
            else:
                dir_name = os.path.dirname(save_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                file_path = save_path
                
            with open(file_path, "wb") as f:
                f.write(result_bytes)
            return {
                "code": 10000,
                "message": "SUCCESS",
                "data": {"save_path": file_path}
            }
        return {
            "code": 10000,
            "message": "SUCCESS",
            "data": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/device/clear-cache")
def clear_cache(payload: ClearCachePayload):
    """Xóa cache của ứng dụng (package) trên thiết bị."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
    device = main_window.adb_handler.device_cache.get(payload.serial)
    if not device:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị {payload.serial}")
    try:
        # Run pm clear <package>
        device.shell(f"pm clear {payload.package}")
        return {"status": "success", "message": f"Đã xóa cache cho {payload.package}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/device/open-app")
def open_app(payload: OpenAppPayload):
    """Mở ứng dụng (package) trên thiết bị."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
    device = main_window.adb_handler.device_cache.get(payload.serial)
    if not device:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị {payload.serial}")
    try:
        # Launch application using monkey generically
        device.shell(f"monkey -p {payload.package} -c android.intent.category.LAUNCHER 1")
        return {"status": "success", "message": f"Đã mở app {payload.package}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/device/type-char")
def type_char(payload: TypeCharPayload):
    """Gõ một ký tự/chuỗi ngắn trên thiết bị."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
    # Call input_text on adb_handler
    main_window.adb_handler.input_text(payload.serial, payload.char)
    return {"status": "success", "message": f"Đã gõ ký tự {payload.char}"}


@app.post("/device/click")
def click_device(payload: DeviceClickPayload):
    """Click vào tọa độ x, y trên thiết bị."""
    if not main_window:
        raise HTTPException(status_code=500, detail="Hệ thống chưa sẵn sàng")
    main_window.adb_handler.tap(payload.serial, payload.x, payload.y)
    return {"status": "success", "message": f"Đã click tại ({payload.x}, {payload.y})"}



def run_api_server(main_window_instance, host: str = "127.0.0.1", default_port: int = 5000):
    """Start the Uvicorn FastAPI server on an available port dynamically."""
    global main_window
    main_window = main_window_instance
    
    current_port = default_port
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, current_port))
            break
        except OSError:
            current_port += 1
            
    api_url = f"http://{host}:{current_port}"
    
    # Thread-safe logging notification back to MainWindow UI log console
    main_window.log_signal.emit(
        f"API Server: {api_url}\n"
        f"Đang quét thiết bị..."
    )
    
    # Start uvicorn server in a non-reload configuration
    config = uvicorn.Config(app, host=host, port=current_port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()
