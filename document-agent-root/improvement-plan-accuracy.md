# Improvement Plan — Độ Chính Xác RegisterBot

> **Mục tiêu:** Giảm tỉ lệ FAILED do bot tap nhầm / nhập sai / không biết đang ở bước nào.
> **Constraint:** Test phải chạy trên máy Windows có cắm BoxPhone thật. Không thêm dependency nặng.
> **Approach:** B (Rule-based verify) + C (Screenshot log mỗi bước)

---

## Giải pháp nền tảng: `uiautomator dump`

Android có sẵn tool `uiautomator dump` — dump toàn bộ UI đang hiển thị ra XML.
Gọi qua endpoint `/api/adb` đã có sẵn:

```
POST /api/adb { serial, command: "uiautomator dump /sdcard/ui.xml" }
POST /api/adb { serial, command: "cat /sdcard/ui.xml" }
```

XML trả về có dạng:
```xml
<node text="招待をリクエストする" bounds="[108,1842][972,1942]" clickable="true" enabled="true"/>
<node text="" resource-id="ap_email" bounds="[54,560][1026,668]" focused="true"/>
```

Từ XML này ta biết:
- Đang ở trang nào (text nào đang visible)
- Tọa độ chính xác từng element (không hardcode nữa)
- Element có enabled/clickable không
- Nội dung của input field

---

## 6 Issues & Plan Chi Tiết

---

### Issue #1 — Không verify sau mỗi bước

**Hiện trạng (code thực tế):**
```python
# phone_bot.py dòng 269
await self._tap_bbox_pct(45, 55, 53, 57, "Nút Request Invitation")
await self._wait_page_load(4.0)   # ← ngủ 4 giây, không biết tap trúng chưa
# Bước tiếp theo chạy ngay, dù tap có trúng hay không
```

**Kết quả mong muốn:**
Sau mỗi bước, bot xác nhận UI đã chuyển sang state kỳ vọng trước khi sang bước tiếp theo.

**Plan:**
1. Tạo `src/screen_reader.py` với hàm `dump_ui(device)` — gọi `/api/adb` + parse XML
2. Tạo hàm `wait_for_text(device, expected_texts, timeout=10)` — poll dump_ui đến khi thấy text
3. Thay `_wait_page_load(N)` bằng `_wait_for_ui(device, expected, timeout=N+5)` tại mỗi step

**Mapping step → expected text sau bước:**
| Sau bước | Expected text xuất hiện (tiếng Nhật) |
|----------|--------------------------------------|
| Step 1: Mở trang sản phẩm | "招待をリクエストする" hoặc "Add to Cart" |
| Step 2: Click Request Invitation | "メールアドレス" hoặc "email" |
| Step 3: Nhập email + Continue | "アカウントの作成" hoặc "パスワード" |
| Step 4: Click Create Account | "氏名" hoặc "お名前" |
| Step 5: Điền form xong | Submit button visible |
| Step 6: Submit form | OTP input visible |
| Step 7: Nhập OTP | URL thay đổi hoặc success message |

**Files thay đổi:**
- Tạo mới: `RegisterBot_Package/src/screen_reader.py`
- Sửa: `RegisterBot_Package/src/phone_bot.py` — thay _wait_page_load bằng _wait_for_ui
- Sửa: `RegisterBot_Package/src/xiaowei_client.py` — thêm `run_adb_shell()`

**Ước lượng:** ~100 dòng code mới

---

### Issue #2 — Screenshot chỉ cuối, mù khi debug

**Hiện trạng (code thực tế):**
```python
# phone_bot.py dòng 328 (register_one) và dòng 419 (register_no_proxy)
await self.xw.screenshot(self.device, screenshot_dir)  # CHỈ 1 ẢNH CUỐI CÙNG
```

Khi FAILED ở bước 3, không có evidence gì để biết bot nhìn thấy gì.

**Kết quả mong muốn:**
Mỗi bước quan trọng có 1 screenshot lưu theo tên bước, timestamp.
Khi mở folder `screenshots/` xem là biết ngay sai ở đâu.

**Plan:**
1. Thêm hàm `_screenshot_step(step_name)` vào `phone_bot.py`:
   ```python
   async def _screenshot_step(self, step_name: str):
       ts = datetime.now().strftime("%H%M%S")
       path = f"data/screenshots/{self.device}/{ts}_{step_name}.png"
       await self.xw.screenshot(self.device, path)
   ```
2. Gọi tại đầu mỗi bước (trước action) và sau mỗi bước quan trọng:
   - Sau Step 1: page load xong
   - Sau Step 2: sau click Request Invitation
   - Sau Step 3: sau nhập email + continue
   - Sau Step 4: sau click Create Account
   - Sau Step 5: sau điền form
   - Sau Step 6: sau submit
   - Sau Step 7: sau nhập OTP
   - Khi FAILED: screenshot ngay trước khi return

**Files thay đổi:**
- Sửa: `RegisterBot_Package/src/phone_bot.py` — thêm `_screenshot_step()` + gọi tại các bước

**Ước lượng:** ~30 dòng code mới

---

### Issue #3 — Tọa độ tap hardcoded

**Hiện trạng (code thực tế):**
```python
# phone_bot.py dòng 269
await self._tap_bbox_pct(45, 55, 53, 57, "Nút Request Invitation")
# X: 45-55%, Y: 53-57% — cứng mãi mãi dù Amazon thay layout
```

**Kết quả mong muốn:**
Bot tìm element theo text trên màn hình → lấy bounds từ XML → tap vào center.
Nếu không tìm được → fallback về hardcoded % + log warning.

**Plan:**
1. Thêm hàm vào `screen_reader.py`:
   ```python
   def find_element_by_text(xml_str, text) -> Optional[dict]:
       # Parse XML, tìm node có text matching
       # Return: { bounds: [x1,y1,x2,y2], center_x, center_y }

   def find_element_by_resource_id(xml_str, resource_id) -> Optional[dict]:
       # Tìm theo resource-id (stable hơn text)
   ```
2. Thêm hàm `_tap_element(device, search_texts, fallback_bbox)` vào `phone_bot.py`:
   ```python
   async def _tap_element(self, search_texts: list, fallback_bbox: tuple, description: str):
       xml = await self.xw.run_adb_shell(self.device, "uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml")
       for text in search_texts:
           elem = screen_reader.find_element_by_text(xml, text)
           if elem:
               log.info(f"Found '{text}' at {elem['center_x']},{elem['center_y']}")
               await self.xw.device_click(self.device, elem["center_x"], elem["center_y"])
               return True
       # Fallback
       log.warning(f"Element not found, using hardcoded bbox for: {description}")
       await self._tap_bbox_pct(*fallback_bbox, description)
       return False
   ```
3. Thay các `_tap_bbox_pct` bằng `_tap_element`:

| Bước hiện tại | search_texts | fallback_bbox |
|---|---|---|
| Request Invitation | `["招待をリクエストする", "Request Invitation"]` | `(45, 55, 53, 57)` |
| Continue (email) | `["続行", "Continue", "次へ"]` | `(45, 55, 53, 57)` |
| Create Account | `["アカウントの作成", "Create your Amazon account"]` | `(40, 60, 48, 52)` |
| Submit form | `["次へ", "Continue", "登録"]` | `(40, 60, 68, 72)` |
| OTP submit | `["アカウントの作成を完了", "Verify"]` | `(40, 60, 58, 62)` |

**Files thay đổi:**
- Sửa: `RegisterBot_Package/src/screen_reader.py` — thêm find_element functions
- Sửa: `RegisterBot_Package/src/phone_bot.py` — thêm `_tap_element()`, thay gọi cũ

**Ước lượng:** ~80 dòng code mới, sửa ~10 chỗ gọi

---

### Issue #4 — Không retry khi API fail

**Hiện trạng (code thực tế):**
```python
# xiaowei_client.py dòng 89-103
async def _post(self, endpoint, payload) -> dict:
    try:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}
        # ← Fail 1 lần → trả về error, không thử lại
```

Khi USB hub bị spike 1 lần, cả flow crash.

**Kết quả mong muốn:**
API call fail → tự retry 3 lần với delay tăng dần (100ms → 300ms → 600ms).
Chỉ raise lỗi khi đã retry hết.

**Plan:**
Sửa `_post()` trong `xiaowei_client.py`:
```python
async def _post(self, endpoint, payload, max_retries=3) -> dict:
    delay_ms = [100, 300, 600]
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = delay_ms[attempt] / 1000
                log.warning(f"[PhoneFarm] Retry {attempt+1}/{max_retries} cho {endpoint} sau {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                log.error(f"[PhoneFarm] Hết retry cho {endpoint}: {e}")
                return {"status": "error", "message": str(e)}
```

**Files thay đổi:**
- Sửa: `RegisterBot_Package/src/xiaowei_client.py` — sửa hàm `_post()`

**Ước lượng:** ~15 dòng code sửa

---

### Issue #5 — Không verify text sau khi nhập

**Hiện trạng (code thực tế):**
```python
# phone_bot.py dòng 274
await self._type_into_field_human(row["email"], 40, 60, 38, 42, "Ô Email")
# Nhập xong không kiểm tra field có đúng không
# Triple-tap + delete có thể không xóa hết, text cũ vẫn còn
```

**Kết quả mong muốn:**
Sau khi type vào field, đọc lại nội dung field từ XML để verify.
Nếu nội dung không khớp → clear và type lại (tối đa 2 lần).

**Plan:**
1. Thêm hàm `get_field_text(device, resource_id)` vào `screen_reader.py`:
   ```python
   def get_field_text(xml_str, resource_id=None, field_index=0) -> str:
       # Parse XML, tìm EditText node, lấy text attribute
   ```
2. Thêm hàm `_type_and_verify(device, text, field_selector, fallback_bbox)` vào `phone_bot.py`:
   ```python
   async def _type_and_verify(self, text, field_hints, bbox, description, max_retry=2):
       for attempt in range(max_retry):
           await self._type_into_field_human(text, *bbox, description)
           await asyncio.sleep(0.5)
           xml = await self.xw.run_adb_shell(self.device, "uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml")
           actual = screen_reader.get_focused_field_text(xml)
           if actual and text.lower() in actual.lower():
               return True
           log.warning(f"Verify fail attempt {attempt+1}: expected '{text}', got '{actual}'")
       return False
   ```
3. Thay các `_type_into_field_human` quan trọng (email, password, OTP) bằng `_type_and_verify`

**Files thay đổi:**
- Sửa: `RegisterBot_Package/src/screen_reader.py` — thêm get_field_text()
- Sửa: `RegisterBot_Package/src/phone_bot.py` — thêm `_type_and_verify()`, thay 5 chỗ gọi

**Ước lượng:** ~60 dòng code mới

---

### Issue #6 — Timeout cứng (sleep thay vì event-driven)

**Hiện trạng (code thực tế):**
```python
# phone_bot.py nhiều chỗ
await self._wait_page_load(5.0)   # ← ngủ đúng 5 giây dù trang load xong sau 1 giây
await self._wait_page_load(4.0)   # ← ngủ đúng 4 giây
# Tổng thời gian cứng: 5+4+4+3+5+5 = 26 giây chỉ để ngủ
```

**Kết quả mong muốn:**
Thay vì sleep cứng, poll UI đến khi có thay đổi (hoặc timeout).
Vừa nhanh hơn (không chờ dư), vừa đúng hơn (biết khi nào trang thực sự load xong).

**Plan:**
1. Thêm hàm `wait_for_ui_change(device, prev_xml, timeout=8)` vào `screen_reader.py`:
   ```python
   async def wait_for_ui_change(self, device, prev_xml, timeout=8, poll_interval=0.5):
       start = time.time()
       while time.time() - start < timeout:
           new_xml = await self.dump_ui(device)
           if new_xml != prev_xml:
               return new_xml  # UI đã thay đổi
           await asyncio.sleep(poll_interval)
       return None  # Timeout — UI không đổi
   ```
2. Thêm hàm `wait_for_text(device, texts, timeout=10)`:
   ```python
   async def wait_for_text(self, device, texts: list, timeout=10, poll_interval=0.8):
       start = time.time()
       while time.time() - start < timeout:
           xml = await self.dump_ui(device)
           for text in texts:
               if find_element_by_text(xml, text):
                   return xml
           await asyncio.sleep(poll_interval)
       return None  # Timeout
   ```
3. Sửa `_wait_page_load` → `_wait_for_ui_change` với timeout = giá trị cũ + 3s buffer

**Files thay đổi:**
- Sửa: `RegisterBot_Package/src/screen_reader.py` — thêm 2 hàm wait
- Sửa: `RegisterBot_Package/src/phone_bot.py` — thay 6 chỗ _wait_page_load

**Ước lượng:** ~50 dòng code mới

---

## Thứ tự implement

Implement theo thứ tự dependency:

```
[1] screen_reader.py (foundation)    ← Issue #1, #3, #5, #6 đều dùng
    ↓
[2] Issue #2: Screenshot mỗi bước   ← Độc lập, làm ngay để debug dễ hơn
    ↓
[3] Issue #4: Retry API             ← Độc lập, làm ngay để ổn định
    ↓
[4] Issue #6: Timeout event-driven  ← Dùng screen_reader
    ↓
[5] Issue #1: Verify sau mỗi bước  ← Dùng screen_reader + #6
    ↓
[6] Issue #3: Dynamic coordinates  ← Dùng screen_reader + #1
    ↓
[7] Issue #5: Verify text input     ← Dùng screen_reader + #3
```

**Lý do thứ tự này:**
- #2 và #4 làm trước vì độc lập, dễ verify, cải thiện ngay việc debug
- screen_reader.py phải xong trước khi làm #6, #1, #3, #5
- #3 (dynamic coordinates) làm sau #1 vì #1 giúp xác nhận #3 hoạt động đúng

---

## File mới cần tạo

### `RegisterBot_Package/src/screen_reader.py`
Foundation class, được dùng bởi tất cả issues:
```python
class ScreenReader:
    def __init__(self, xiaowei_client):
        self.xw = xiaowei_client

    async def dump_ui(self, device) -> str:
        """Dump UI hierarchy XML từ thiết bị."""
        ...

    def find_element_by_text(self, xml_str, text, partial=True) -> Optional[dict]:
        """Tìm element theo text. Return {x1,y1,x2,y2,cx,cy}."""
        ...

    def find_element_by_resource_id(self, xml_str, resource_id) -> Optional[dict]:
        """Tìm element theo resource-id."""
        ...

    def get_focused_field_text(self, xml_str) -> Optional[str]:
        """Lấy nội dung field đang focused."""
        ...

    async def wait_for_text(self, device, texts, timeout=10) -> Optional[str]:
        """Poll đến khi thấy bất kỳ text nào trong list."""
        ...

    async def wait_for_ui_change(self, device, prev_xml, timeout=8) -> Optional[str]:
        """Poll đến khi UI thay đổi."""
        ...
```

---

## Log Kết Quả (cập nhật sau mỗi issue)

### screen_reader.py (foundation)
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** `dump_ui()` trả về XML hợp lệ, `find_element_by_text()` tìm được element
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **File tạo:** `RegisterBot_Package/src/screen_reader.py` (269 dòng)
- **Notes:**
  - `dump_ui()` gọi 2 lệnh ADB liên tiếp: `uiautomator dump` + `cat`
  - `has_any_text()` dùng string search (không parse XML) để nhanh trong poll loop
  - `wait_for_text()` poll 0.8s, `wait_for_ui_change()` poll 0.5s
  - Không cần dependency nào ngoài stdlib (xml.etree, re, asyncio)

### Issue #2 — Screenshot mỗi bước
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Folder `data/screenshots/{serial}/` có ảnh từng bước, tên `HHMMSS_stepname.png`
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - Thêm `_screenshot_step(step_name)` vào `PhoneRegistrationBot`
  - `register_no_proxy()`: 8 điểm chụp (step1 → step5c_final_result)
  - `register_one()`: 11 điểm chụp (step1 → step8_final_result)
  - Chụp screenshot ngay khi FAILED (trước khi return) để debug
  - `_screenshot_step()` không raise exception — bot tiếp tục dù chụp thất bại

### Issue #4 — Retry API
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Khi USB spike 1 lần, bot tự retry và tiếp tục
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - `_post()` trong `xiaowei_client.py`: retry 3 lần với delay 100ms/300ms/600ms
  - Retry khi: ConnectError, TimeoutException, HTTP 5xx
  - Không retry khi: HTTP 4xx (lỗi client — retry vô ích)
  - Log rõ attempt thứ mấy, delay bao lâu

### Issue #6 — Timeout event-driven
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Bot không chờ dư giây, phát hiện trang load xong và tiếp tục
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - Thêm `_wait_for_state(expected_texts, timeout, step_name)` vào `phone_bot.py`
  - Non-blocking: timeout chỉ log warning + chụp screenshot, bot KHÔNG dừng
  - `register_no_proxy()`: thay 3 chỗ sleep cứng bằng event-driven wait
  - `register_one()`: thay 5 chỗ `_wait_page_load()` bằng event-driven wait
  - Fallback: nếu `_wait_for_state()` timeout → sleep ngắn thêm rồi tiếp tục
  - Kỳ vọng: giảm thời gian đăng ký 1 account từ ~60s → ~35-40s

### Issue #1 — Verify sau mỗi bước
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Bot biết chính xác mình đang ở bước nào, dừng và báo lỗi đúng chỗ
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - Implement thông qua `_wait_for_state()` (xem Issue #6)
  - Sau mỗi action, bot wait text kỳ vọng → confirm bước đó thành công
  - Mapping step→text trong comment code

### Issue #3 — Dynamic coordinates
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Bot tìm nút theo text, không cần cập nhật code khi Amazon đổi layout
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - Thêm `_tap_element(search_texts, fallback_bbox, description)` vào `phone_bot.py`
  - `register_no_proxy()`: Create Account, Verify Email, Confirm OTP → dùng dynamic tap
  - `register_one()`: Request Invitation, Continue, Create Account, Submit, Xác minh OTP
  - Thinking delay 1.5-3.0s vẫn giữ nguyên trong `_tap_element()`
  - Luôn có fallback bbox → không bao giờ crash nếu uiautomator fail

### Issue #5 — Verify text input
- **Ngày implement:** 2026-06-28
- **Kết quả mong muốn:** Email/OTP được verify sau khi nhập, tự retry nếu sai
- **Kết quả thực tế sau test:** Chưa test (cần Windows + BoxPhone thật)
- **Hiệu quả:** Chờ test
- **Notes:**
  - Thêm `_type_and_verify(text, bbox, description, is_password)` vào `phone_bot.py`
  - `is_password=True` → skip verify (uiautomator không đọc được password)
  - Verify: dump_ui → `get_focused_field_text()` → so sánh với text đã nhập
  - Max retry: 2 lần. Nếu cả 2 lần sai → log error nhưng bot tiếp tục (không crash)
  - Áp dụng cho: email field, OTP field (cả 2 flow)
  - Không áp dụng cho: password, confirm password (is_password=True)
