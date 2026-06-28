# 07 — Hiện Trạng & Roadmap

## Trạng thái hệ thống (tính đến 2026-06-28)

**Hệ thống đã chạy được end-to-end.** Evidence:
- Backup files dated 2026-06-21 → đã có batch chạy thực tế
- Screenshots trong `logs/` dated 2026-06-27 (device `RF8M20J4VBX`) → bot đã điều khiển điện thoại thực
- Device đang được test: `R58M30WAT1F` và `RF8M20J4VBX`
- Build `.exe` đã có trong `RegisterBot_Package/dist/`

---

## Đã hoàn thiện

- [x] PyQt6 GUI điều khiển điện thoại
- [x] ADB tap/swipe/text/keyevent/screenshot
- [x] scrcpy stream nhúng vào card (Win32 HWND)
- [x] FastAPI REST server :5000
- [x] Flask dashboard :8000 + SSE log stream
- [x] Gmail IMAP OTP reader (poll 3s, timeout 90s)
- [x] Excel input/output (styled: green/red)
- [x] SQLite databases (cả 2 component)
- [x] Proxy pool + data usage + rotation
- [x] Human typing simulation (80–220ms, typo 5%)
- [x] Anti-detection (URL random, Japanese name gen, thinking delay)
- [x] PyInstaller build thành `.exe`
- [x] Phone mode (điện thoại thật qua ADB)
- [x] Browser mode (Playwright — fallback)
- [x] Auto port scan (5000, 8000)
- [x] Staggered scrcpy start (tránh bão USB)
- [x] ADB rate limiting 100ms (bảo vệ USB hub)

---

## Còn thiếu / Điểm yếu

### P1 — Quan trọng, ảnh hưởng độ ổn định

| Vấn đề | Mô tả | Hướng xử lý |
|--------|-------|-------------|
| **Tọa độ hardcoded** | Bot tap vào % cứng, nếu Amazon thay layout thì vỡ | Thêm OCR/Vision để tìm element theo text/màu sắc |
| **Không có screen reading** | Bot không biết màn hình đang ở step nào, không verify sau mỗi action | Thêm screenshot + image analysis sau mỗi bước quan trọng |
| **Retry dumb** | Khi bị kẹt chỉ retry blindly, không biết nguyên nhân | State machine rõ ràng + retry có điều kiện |

### P2 — Cải thiện hiệu suất/scale

| Vấn đề | Mô tả | Hướng xử lý |
|--------|-------|-------------|
| **1 Gmail master** | 1 Gmail nhận OTP cho tất cả account → bottleneck và dễ bị Gmail block | Pool Gmail accounts, rotate theo batch |
| **Không có health check** | Không biết device offline cho đến khi thực sự chạy | Heartbeat check ADB connection mỗi 30s |
| **Log khó đọc** | Log là text stream, không có structured format | Thêm level, timestamp, device serial vào mỗi log line |

### P3 — Tiện ích / Vận hành

| Vấn đề | Mô tả |
|--------|-------|
| **Setup thủ công** | Phải cài adb/scrcpy/Python tay trên máy mới |
| **Không có analytics** | Không có tỉ lệ success/fail theo device, theo batch |
| **Config phân tán** | `src/config.py` + `data/config.json` + `.env` — dễ nhầm lẫn |

---

## Session tiếp theo nên làm gì

Ưu tiên gợi ý:
1. **Chạy thử và capture screenshot từng bước** → xác định tọa độ thực tế trên device đang dùng
2. **Thêm verify sau mỗi bước** → so sánh screenshot với expected state
3. **Cải thiện error messages** → log rõ đang fail ở bước nào, tại sao
