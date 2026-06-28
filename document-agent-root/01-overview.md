# 01 — Tổng Quan Dự Án

## Dự án làm gì

**AMA-Tool** tự động đăng ký hàng loạt tài khoản **Amazon Nhật Bản** (`amazon.co.jp`) bằng cách điều khiển các điện thoại Android vật lý (BoxPhone) cắm USB vào máy Windows.

**Bài toán:** Amazon JP có Invitation Program — cần tài khoản để mua sản phẩm giới hạn. Đăng ký thủ công chậm và bị block khi dùng nhiều account từ cùng 1 IP/device.

**Giải pháp:** Mỗi điện thoại Android = 1 danh tính độc lập (browser fingerprint riêng + proxy IP riêng + session riêng). N điện thoại chạy song song = N account được tạo cùng lúc.

## 2 Component chính

| Component | Thư mục | Vai trò |
|---|---|---|
| **Phone Farm** | `android_phone_farm/` | GUI quản lý điện thoại + REST API điều khiển device |
| **Register Bot** | `RegisterBot_Package/` | Logic đăng ký Amazon + đọc OTP Gmail + ghi kết quả |

Hai component giao tiếp qua HTTP localhost. Xem chi tiết: [02-architecture.md](02-architecture.md)

## Môi trường chạy

| Thành phần | Yêu cầu |
|---|---|
| **OS** | **Windows only** — dùng Win32 API nhúng màn hình điện thoại vào GUI |
| **Python** | 3.10+ |
| **ADB** | Android Debug Bridge (giao tiếp USB) |
| **scrcpy** | Stream màn hình điện thoại về PC (v4.0+) |
| **Điện thoại Android** | Bật USB Debugging, cắm USB |
| **Gmail** | 1 account + App Password 16 ký tự (nhận OTP Amazon) |
| **macOS/Linux** | **KHÔNG hỗ trợ** |

## Input / Output tóm tắt

- **Input:** File `accounts.xlsx` (email + password cần tạo) + điện thoại cắm USB
- **Output:** `results.xlsx` (SUCCESS/FAILED) + `registered_accounts.db`
- Chi tiết đầy đủ: [03-input-output.md](03-input-output.md)
