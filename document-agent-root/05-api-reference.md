# 05 — API Reference

## Phone Farm API (FastAPI — port 5000)

Base URL: `http://127.0.0.1:5000`
> Port có thể thay đổi nếu 5000 bị bận. Xem log sidebar GUI để biết port thực tế.

### Target Convention
Mọi POST đều hỗ trợ 3 kiểu target:
```json
{ "serial": "R58M35HG87Y" }           // 1 device
{ "serials": ["DEV1", "DEV2"] }        // nhiều device
{ "serials": "all" }                    // tất cả device online
```

### Endpoints

#### GET /api/devices
Danh sách device đang kết nối.
```json
// Response
[
  {
    "serial": "R58M35HG87Y",
    "resolution": "1080x2400",
    "is_streaming": true,
    "is_selected": true
  }
]
```

#### POST /api/tap
Click tọa độ trên màn hình.
```json
// Pixel tuyệt đối
{ "serial": "R58M35HG87Y", "x": 540, "y": 1200 }

// Phần trăm màn hình (khuyến nghị — dùng khi nhiều device khác resolution)
{ "serials": "all", "x_pct": 0.5, "y_pct": 0.5 }
```

#### POST /api/swipe
Vuốt màn hình.
```json
{
  "serial": "R58M35HG87Y",
  "x1_pct": 0.5, "y1_pct": 0.8,
  "x2_pct": 0.5, "y2_pct": 0.2,
  "duration": 400
}
```

#### POST /api/text
Nhập text vào input đang active. Tự động escape space → `%s`.
```json
{ "serial": "R58M35HG87Y", "text": "hello world 123" }
```

#### POST /api/keyevent
Phím cứng Android.
```json
{ "serial": "R58M35HG87Y", "keycode": 4 }
```
Keycodes: HOME=3, BACK=4, POWER=26, ENTER=66, DEL=67, MENU=82

#### POST /api/screenshot
Chụp màn hình, lưu vào `data/screenshots/{serial}.png`.
```json
{ "serial": "R58M35HG87Y" }
```

#### GET /api/proxy?serial=XXX
Proxy đang gán cho device.

#### POST /api/proxy/rotate
Xoay sang proxy mới từ pool.
```json
{ "serial": "R58M35HG87Y" }
```

#### GET /api/data_usage
Dung lượng data đã dùng + quota limit mỗi device.

#### POST /api/stream
Bật/tắt scrcpy stream.
```json
{ "serial": "R58M35HG87Y", "action": "start" }
{ "serial": "R58M35HG87Y", "action": "stop" }
```

#### POST /device/clear-cache
Xóa cache app.
```json
{ "serial": "R58M35HG87Y", "package": "org.mozilla.firefox" }
```

#### POST /device/open-app
Mở app.
```json
{ "serial": "R58M35HG87Y", "package": "org.mozilla.firefox" }
```

#### POST /device/type-char
Gõ 1 ký tự (dùng trong human_type loop).
```json
{ "serial": "R58M35HG87Y", "char": "a" }
```

#### POST /device/click
Click pixel tuyệt đối.
```json
{ "serial": "R58M35HG87Y", "x": 540, "y": 1200 }
```

---

## RegisterBot Dashboard (Flask — port 8000)

Base URL: `http://127.0.0.1:8000`

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Web UI dashboard |
| POST | `/api/start` | Start bot. Body: `{ group_name, product_url }` |
| POST | `/api/stop` | Stop bot |
| GET | `/api/status` | `{ status: "IDLE" \| "RUNNING" \| "STOPPING" }` |
| GET | `/api/results` | Danh sách kết quả đã chạy |
| POST | `/api/config` | Cập nhật config runtime |
| GET | `/api/logs` | SSE stream log realtime |
| GET | `/api/devices` | Proxy sang Phone Farm :5000 lấy device list |
| GET | `/download/results` | Tải file results.xlsx |

---

## Python Client Mẫu

```python
import time, requests

API = "http://127.0.0.1:5000"

# Lấy danh sách device
devices = requests.get(f"{API}/api/devices").json()
serial = devices[0]["serial"]

# Click giữa màn hình
requests.post(f"{API}/api/tap", json={"serial": serial, "x_pct": 0.5, "y_pct": 0.5})
time.sleep(1)

# Nhập text
requests.post(f"{API}/api/text", json={"serial": serial, "text": "hello 123"})
time.sleep(1)

# Nhấn ENTER
requests.post(f"{API}/api/keyevent", json={"serial": serial, "keycode": 66})
```
