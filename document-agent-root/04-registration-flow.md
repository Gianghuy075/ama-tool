# 04 — Luồng Đăng Ký Amazon (8 Bước)

## Tổng quan

Mỗi account được xử lý bởi `PhoneRegistrationBot` trong `src/phone_bot.py`.
Bot gọi `XiaoWeiClient` → HTTP POST → Phone Farm API :5000 → ADB → điện thoại.

## 8 Bước Chi Tiết

### Bước 1: Clear cache + Mở trình duyệt
```
POST /device/clear-cache { serial, package: "org.mozilla.firefox" }
    → adb shell pm clear org.mozilla.firefox

POST /device/open-app { serial, package: "org.mozilla.firefox" }
    → adb shell am start ...
```
**Lý do clear cache:** Xóa cookies/session cũ, tránh Amazon nhận ra đây là thiết bị đã dùng.

### Bước 2: Navigate tới sản phẩm
```
Click address bar → human_type(product_url) → ENTER
product_url có random tokens: ?ref=xxx&fbclid=xxx (anti-detection)
```

### Bước 3: Click "Request Invitation"
```
Tìm nút "招待をリクエストする" trên trang
→ POST /api/tap { serial, x_pct: 0.5, y_pct: 0.7 }  (tọa độ % hardcoded)
→ thinking_delay() 0.8–1.8s trước khi click
```
**Điểm yếu hiện tại:** Tọa độ hardcoded — nếu Amazon thay layout thì vỡ.

### Bước 4: Nhập email
```
Tìm input[type=email] → click → human_type(email)
human_type: gõ từng ký tự 80–220ms, 5% typo simulation
→ POST /api/keyevent { keycode: 66 }  (ENTER)
```

### Bước 5: Phân nhánh — email mới hay cũ?
```
POST /api/screenshot → phân tích nội dung màn hình

Nếu thấy "アカウントの作成に進む" (Tạo tài khoản mới):
    → click nút đó → tiếp tục bước 6

Nếu thấy form đăng nhập (email đã tồn tại):
    → status = FAILED, note = "Email đã có account Amazon"
    → bỏ qua account này
```

### Bước 6: Điền form đăng ký
```
Name field:     human_type(name)       # tên Nhật nếu không có thì sinh ngẫu nhiên
Password:       human_type(password)
Confirm pass:   human_type(password)

Mỗi field: thinking_delay() trước, scroll để field vào view trước khi type
```

### Bước 7: Submit form
```
Tìm button[type=submit] → thinking_delay() → POST /api/tap
```

### Bước 8: Chờ và nhập OTP
```
GmailOTPReader.fetch_otp(email, wait_seconds=90):
    Loop mỗi 3 giây:
        IMAP connect → search email từ amazon* gửi sau T
        Filter: sender=amazon*, time>=T-60s, recipient=email đích
        Extract: regex r'\b\d{6}\b' từ body
    Return: OTP string hoặc None (timeout)

Nếu có OTP:
    human_type(OTP) → ENTER → chờ redirect → SUCCESS

Nếu timeout 90s:
    status = FAILED, note = "OTP timeout"
```

## Trạng thái kết quả

| Status | Lý do |
|--------|-------|
| SUCCESS | OTP nhập đúng, account được tạo |
| FAILED | Email đã tồn tại |
| FAILED | OTP timeout (90s) |
| FAILED | Form error (validation Amazon) |
| FAILED | Device offline / ADB lỗi |
| FAILED | Amazon block / CAPTCHA |

## Anti-Detection trong flow

| Kỹ thuật | Vị trí áp dụng |
|----------|---------------|
| URL random tokens | Bước 2 — mỗi account URL khác nhau |
| Thinking delay 0.8–1.8s | Trước mỗi click |
| Human typing 80–220ms/char | Bước 4, 6, 8 |
| Typo simulation 5% | Bước 4, 6 |
| Scroll trước interact | Bước 3, 6 |
| Random Japanese name | Bước 6 nếu name rỗng |

## Code liên quan

- `RegisterBot_Package/src/phone_bot.py` — PhoneRegistrationBot class
- `RegisterBot_Package/src/xiaowei_client.py` — HTTP client → API :5000
- `RegisterBot_Package/src/gmail_otp.py` — IMAP OTP reader
- `RegisterBot_Package/src/config.py` — CONFIG["xiaowei"]["human_typing"]
