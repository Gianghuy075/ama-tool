# Tài Liệu Hướng Dẫn Kết Nối & Điều Khiển Thiết Bị Qua API (Android Phone Farm)

Tài liệu này tổng hợp các REST API được cung cấp bởi hệ thống Android Phone Farm (chạy từ file [api_server.py](file:///c:/Users/Admin/.gemini/antigravity/scratch/android_phone_farm/api_server.py)) để bạn có thể lập trình, kết nối với công cụ (tool) của mình và tự động hóa thao tác điều khiển trên các điện thoại Android đang kết nối.

---

## 1. Thông Tin Chung & Khởi Động

*   **Địa chỉ API Server mặc định:** `http://127.0.0.1:5000`
*   **Cơ chế quét cổng tự động:** Nếu cổng `5000` đang bị chiếm bởi phần mềm khác, API Server sẽ tự động tăng dần cổng (`5001`, `5002`,...) cho đến khi tìm thấy cổng rảnh.
*   **Cách kiểm tra cổng đang chạy:** Bạn có thể xem trực tiếp địa chỉ API Server tại dòng log ở phần Sidebar phía dưới cùng của giao diện chính (GUI).
*   **Quy ước Target (Mục tiêu nhận lệnh):** Hầu hết các API dạng `POST` (như click, vuốt, nhập text, keyevent) đều hỗ trợ gửi lệnh đồng thời đến một hoặc nhiều thiết bị bằng cách truyền tham số target trong body request:
    *   **Điều khiển 1 thiết bị:** Truyền `"serial": "DEVICE_SERIAL"`
    *   **Điều khiển danh sách thiết bị:** Truyền `"serials": ["SERIAL_1", "SERIAL_2"]`
    *   **Điều khiển tất cả thiết bị online:** Truyền `"serials": "all"`

---

## 2. Danh Sách Chi Tiết Các API

### 2.1. Lấy Danh Sách Thiết Bị Kết Nối (`GET /api/devices`)

Lấy toàn bộ danh sách các điện thoại Android đang cắm cáp kết nối và trạng thái hiện tại của chúng.

*   **URL:** `/api/devices`
*   **Method:** `GET`
*   **Mẫu phản hồi (Response):**
    ```json
    [
      {
        "serial": "R58M35HG87Y",
        "resolution": "1080x2400",
        "is_streaming": true,
        "is_master": false,
        "is_selected": true
      },
      {
        "serial": "192.168.1.50:5555",
        "resolution": "720x1280",
        "is_streaming": false,
        "is_master": false,
        "is_selected": false
      }
    ]
    ```

---

### 2.2. Giả Lập Click/Tap (`POST /api/tap`)

Gửi sự kiện Click (Tap) tại một tọa độ chỉ định trên màn hình thiết bị. Bạn có thể chỉ định theo tọa độ Pixel tuyệt đối hoặc theo tỉ lệ phần trăm `%` (độ phân giải sẽ tự quy đổi).

*   **URL:** `/api/tap`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial` hoặc `serials` (Xem quy ước Target)
    *   *Lựa chọn 1 (Tọa độ tuyệt đối):* `x` (int) và `y` (int)
    *   *Lựa chọn 2 (Tỉ lệ phần trăm màn hình - khuyến nghị khi chạy đa thiết bị khác màn hình):* `x_pct` (float, từ `0.0` đến `1.0`) và `y_pct` (float, từ `0.0` đến `1.0`)
*   **Mẫu Payload:**
    *   **Theo Pixel tuyệt đối:**
        ```json
        {
          "serials": ["R58M35HG87Y"],
          "x": 540,
          "y": 1200
        }
        ```
    *   **Theo tỉ lệ % (Click giữa màn hình):**
        ```json
        {
          "serials": "all",
          "x_pct": 0.5,
          "y_pct": 0.5
        }
        ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã gửi lệnh Tap tới 1 thiết bị"
    }
    ```

---

### 2.3. Giả Lập Vuốt Màn Hình/Swipe (`POST /api/swipe`)

Gửi sự kiện Vuốt (Swipe) kéo từ điểm bắt đầu sang điểm kết thúc với khoảng thời gian duy trì nhất định.

*   **URL:** `/api/swipe`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial` hoặc `serials`
    *   *Tọa độ bắt đầu & kết thúc tuyệt đối:* `x1`, `y1`, `x2`, `y2` (int)
    *   *Hoặc Tọa độ bắt đầu & kết thúc dạng %:* `x1_pct`, `y1_pct`, `x2_pct`, `y2_pct` (float)
    *   `duration`: Thời gian vuốt tính bằng miligiây (int, mặc định `300` nếu không truyền)
*   **Mẫu Payload (Vuốt từ dưới lên để cuộn trang):**
    ```json
    {
      "serial": "R58M35HG87Y",
      "x1_pct": 0.5,
      "y1_pct": 0.8,
      "x2_pct": 0.5,
      "y2_pct": 0.2,
      "duration": 400
    }
    ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã gửi lệnh Swipe tới 1 thiết bị"
    }
    ```

---

### 2.4. Nhập Văn Bản (`POST /api/text`)

Gõ một chuỗi văn bản (chữ không dấu hoặc ký tự đặc biệt) vào ô nhập liệu đang active trên điện thoại.

*   **URL:** `/api/text`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial` hoặc `serials`
    *   `text`: Chuỗi văn bản muốn gõ (string)
*   **Mẫu Payload:**
    ```json
    {
      "serials": "all",
      "text": "chao cac ban 123"
    }
    ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã gửi văn bản nhập tới 2 thiết bị"
    }
    ```

> [!NOTE]
> Để gõ văn bản có chứa khoảng trắng thông qua ADB, hệ thống đã tự động mã hóa dấu khoảng trắng thành `%s` trước khi truyền xuống thiết bị, bạn chỉ cần gửi chuỗi văn bản thuần túy của bạn qua API.

---

### 2.5. Giả Lập Phím Cứng/Keyevent (`POST /api/keyevent`)

Gửi mã phím vật lý của hệ điều hành Android (Home, Back, Nguồn, Tăng/Giảm âm lượng, Enter, Xóa,...).

*   **URL:** `/api/keyevent`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial` hoặc `serials`
    *   `keycode`: Mã keycode của Android (int). Một số mã phổ biến:
        *   `3`: Phím HOME
        *   `4`: Phím BACK (Trở lại)
        *   `26`: Phím POWER (Bật/Tắt màn hình)
        *   `66`: Phím ENTER (Đồng ý)
        *   `67`: Phím DEL (Xóa ký tự)
        *   `82`: Phím MENU
*   **Mẫu Payload (Bấm nút BACK quay lại):**
    ```json
    {
      "serial": "R58M35HG87Y",
      "keycode": 4
    }
    ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã gửi Keyevent 4 tới 1 thiết bị"
    }
    ```

---

### 2.6. Lấy Proxy Đang Gán Của Thiết Bị (`GET /api/proxy`)

Truy vấn thông tin chi tiết proxy hiện hành mà thiết bị đang được gán từ Proxy Pool trong cơ sở dữ liệu SQLite.

*   **URL:** `/api/proxy?serial=DEVICE_SERIAL`
*   **Method:** `GET`
*   **Mẫu phản hồi:**
    ```json
    {
      "serial": "R58M35HG87Y",
      "has_proxy": true,
      "proxy": "125.235.12.34:8080:user123:pass123",
      "ip": "125.235.12.34",
      "port": 8080,
      "username": "user123",
      "password": "pass123",
      "status": "live"
    }
    ```

---

### 2.7. Xoay IP/Đổi Proxy Mới (`POST /api/proxy/rotate`)

Bắt buộc hệ thống thay đổi IP hoặc đổi sang một Proxy khác đang rảnh trong cơ sở dữ liệu cho thiết bị chỉ định.

*   **URL:** `/api/proxy/rotate`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial`: Serial thiết bị cần xoay IP (string)
*   **Mẫu Payload:**
    ```json
    {
      "serial": "R58M35HG87Y"
    }
    ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã xoay IP cho thiết bị R58M35HG87Y"
    }
    ```

---

### 2.8. Xem Thống Kê Dung Lượng Mạng (`GET /api/data_usage`)

Kiểm tra dung lượng mạng tiêu thụ (Receive + Transmit) của tất cả thiết bị và xem máy nào đang bị chặn mạng do vượt hạn mức giới hạn (quota).

*   **URL:** `/api/data_usage`
*   **Method:** `GET`
*   **Mẫu phản hồi:**
    ```json
    [
      {
        "serial": "R58M35HG87Y",
        "total_bytes_used": 157286400,
        "total_mb_used": 150.0,
        "quota_limit_bytes": 1073741824,
        "quota_limit_mb": 1024.0,
        "is_blocked": false
      }
    ]
    ```

---

### 2.9. Bật/Tắt Luồng Stream Scrcpy (`POST /api/stream`)

Điều khiển bật hoặc tắt truyền hình ảnh màn hình điện thoại về máy tính qua Scrcpy từ xa.

*   **URL:** `/api/stream`
*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Tham số Body Request:**
    *   `serial`: Serial thiết bị (string)
    *   `action`: `"start"` để bật stream, hoặc `"stop"` để tắt stream (string)
*   **Mẫu Payload:**
    ```json
    {
      "serial": "R58M35HG87Y",
      "action": "start"
    }
    ```
*   **Mẫu phản hồi:**
    ```json
    {
      "status": "success",
      "message": "Đã gửi lệnh start stream tới R58M35HG87Y"
    }
    ```

---

## 3. Mẫu Code Python Tích Hợp Ví Dụ

Dưới đây là một script mẫu bằng Python sử dụng thư viện `requests` để điều khiển tự động chuỗi hành động: kiểm tra danh sách máy, click vào màn hình, gõ chữ và bấm Back.

```python
import time
import requests

API_URL = "http://127.0.0.1:5000"

def get_devices():
    res = requests.get(f"{API_URL}/api/devices")
    return res.json()

def auto_control():
    # 1. Lấy danh sách máy đang chạy
    devices = get_devices()
    if not devices:
        print("Không tìm thấy thiết bị nào đang kết nối!")
        return
        
    # Chọn thiết bị đầu tiên
    serial = devices[0]["serial"]
    print(f"Đang tự động điều khiển thiết bị: {serial}")
    
    # 2. Click (Tap) tại giữa màn hình (tọa độ tỷ lệ %)
    tap_payload = {
        "serial": serial,
        "x_pct": 0.5,
        "y_pct": 0.5
    }
    requests.post(f"{API_URL}/api/tap", json=tap_payload)
    time.sleep(1)
    
    # 3. Gõ chữ vào ô nhập liệu
    text_payload = {
        "serial": serial,
        "text": "hello tu dong hoa"
    }
    requests.post(f"{API_URL}/api/text", json=text_payload)
    time.sleep(1)
    
    # 4. Nhấn phím Back để ẩn bàn phím hoặc quay lại
    key_payload = {
        "serial": serial,
        "keycode": 4
    }
    requests.post(f"{API_URL}/api/keyevent", json=key_payload)
    print("Hoàn thành chuỗi hành động điều khiển tự động.")

if __name__ == "__main__":
    auto_control()
```
