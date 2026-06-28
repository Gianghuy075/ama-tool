# 08 — Session History

> Mỗi session làm việc **phải append vào file này** trước khi kết thúc.
> Format chuẩn bên dưới. Ghi đủ để session sau hiểu ngay không cần hỏi lại.

---

## Template

```
### Session YYYY-MM-DD — [Tiêu đề ngắn]
**Người thực hiện:** [tên/role]
**Branch/PR:** (nếu có)

**Đã làm:**
- Bullet point từng việc

**Phát hiện quan trọng:**
- Những điều không hiển nhiên, cần biết về sau

**Kết quả:**
- Thành công / Thất bại / Partial

**Ảnh hưởng:**
- File nào thay đổi, behavior nào thay đổi

**Còn lại / Session sau làm:**
- Việc chưa xong hoặc gợi ý tiếp theo
```

---

## Lịch sử

### Session 2026-06-28 — Phân tích toàn bộ codebase + Tạo tài liệu
**Người thực hiện:** Orchestrator AI (Claude Sonnet)

**Đã làm:**
- Đọc toàn bộ source code cả 2 component
- Phân tích kiến trúc, flow, API, DB schema, anti-detection
- Tạo folder `document-agent-root/` với 8 file tài liệu chuyên biệt
- Cập nhật `CLAUDE.md` thành index ngắn gọn (không chứa nội dung)

**Phát hiện quan trọng:**
- Bot đã chạy thực tế (screenshots ngày 2026-06-27 trong `logs/`)
- 2 device đã được dùng: `R58M30WAT1F` và `RF8M20J4VBX`
- Điểm yếu lớn nhất: tọa độ tap hardcoded theo % — dễ vỡ khi Amazon thay layout
- `xiaowei_client.py` hỗ trợ cả `phone_farm` mode (HTTP REST) và `xiaowei` mode (WebSocket legacy) — hiện chỉ dùng `phone_farm`
- Gmail `pokemontt0008@gmail.com` đang được dùng — App Password có trong config.json

**Kết quả:** Tài liệu đầy đủ, sẵn sàng cho AI agent tiếp theo

**Ảnh hưởng:**
- Tạo mới: `CLAUDE.md`, `document-agent-root/` (8 files)
- Không thay đổi logic code

**Còn lại / Session sau làm:**
- Xem [07-current-status.md](07-current-status.md) phần "Session tiếp theo"

---

### Session 2026-06-28 — Implement 6 Accuracy Improvements
**Người thực hiện:** Orchestrator AI (Claude Sonnet)

**Đã làm:**
- Tạo mới `RegisterBot_Package/src/screen_reader.py` (269 dòng) — foundation module
- Sửa `RegisterBot_Package/src/phone_bot.py`:
  - Fix bug: thêm `import os` (trước đó dùng `os.makedirs` mà thiếu import)
  - Import `ScreenReader`, khởi tạo `self.screen_reader` trong `__init__`
  - Thêm `_screenshot_step()` — chụp ảnh tại mỗi step, lưu vào `data/screenshots/{serial}/`
  - Thêm `_wait_for_state()` — đợi text kỳ vọng xuất hiện thay vì sleep cứng
  - Thêm `_tap_element()` — tìm element theo text từ uiautomator XML, fallback bbox
  - Thêm `_type_and_verify()` — type text rồi verify nội dung field qua uiautomator
  - Thay `_wait_page_load()` bằng `_wait_for_state()` tại 8 chỗ trong 2 flow
  - Thay `_tap_bbox_pct()` bằng `_tap_element()` tại các nút quan trọng
  - Thay `_type_into_field_human()` bằng `_type_and_verify()` cho email + OTP
  - Thêm 11 điểm chụp screenshot trong `register_one()`, 8 điểm trong `register_no_proxy()`
- Sửa `RegisterBot_Package/src/xiaowei_client.py`:
  - `_post()`: thêm retry 3 lần với backoff 100/300/600ms
  - Retry khi: ConnectError, Timeout, HTTP 5xx — không retry HTTP 4xx
- Cập nhật `document-agent-root/improvement-plan-accuracy.md` với log kết quả implement
- Cập nhật `document-agent-root/08-session-history.md`

**Phát hiện quan trọng:**
- `_tap_element()` giữ nguyên thinking delay 1.5-3.0s để không break anti-detection
- Tất cả improvements đều non-blocking: timeout/fail chỉ log warning, bot tiếp tục
- `is_password=True` trong `_type_and_verify()` là bắt buộc — Android ẩn password trong uiautomator
- Kỳ vọng giảm thời gian đăng ký: ~60s → ~35-40s (nhờ event-driven wait)

**Kết quả:**
- Implement xong 100% 6 issues. Syntax check OK (Python ast.parse)
- Chưa test thực tế — cần Windows + BoxPhone thật

**Ảnh hưởng:**
- Tạo mới: `RegisterBot_Package/src/screen_reader.py`
- Sửa: `RegisterBot_Package/src/phone_bot.py` (thêm ~130 dòng, sửa ~40 dòng)
- Sửa: `RegisterBot_Package/src/xiaowei_client.py` (sửa `_post()`, thêm ~20 dòng)
- Sửa: `document-agent-root/improvement-plan-accuracy.md` (log kết quả)

**Còn lại / Session sau làm:**
- Test thực tế trên Windows + BoxPhone — ghi kết quả vào log table trong `improvement-plan-accuracy.md`
- Nếu uiautomator text không match (tiếng Nhật thực tế trên app khác plan) → update search_texts list
- Kiểm tra path lưu screenshot có đúng trên Windows không (dùng `os.path.join` đã OK)
- Cân nhắc thêm `run_adb` (fire-and-forget, không cần output) vào `xiaowei_client.py` nếu thiếu
