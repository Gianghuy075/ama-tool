# Hướng Dẫn Vận Hành Tự Động Hóa Đăng Ký (Chạy Cục Bộ - Local)

Tài liệu này hướng dẫn cách chạy phần mềm trên máy tính của bạn, cách đưa danh sách tài khoản vào và cấu hình Gmail Master để tự động quét mã OTP.

---

## 1. Hướng Dẫn Chạy Tool Trên Máy Local

Để chạy giao diện quản lý thiết bị và thực hiện đăng ký tài khoản tự động, hãy làm theo các bước sau:

### Bước 1: Cài đặt thư viện Python cần thiết
Mở Terminal/CMD tại thư mục gốc của dự án (`GDP-ToolAma-main`) và chạy lệnh cài đặt các thư viện phụ thuộc:
```bash
pip install PyQt6 PyQt6-DarkTheme pandas openpyxl ppadb httpx uvicorn fastapi requests
```

### Bước 2: Khởi động giao diện điều khiển (PyQt App)
Di chuyển vào thư mục `android_phone_farm` và chạy file `main.py`:
```bash
cd android_phone_farm
python main.py
```
> **Lưu ý:** Giao diện tối màu cao cấp của tool sẽ hiển thị. Tool sẽ tự quét các cổng kết nối USB của máy tính để tìm kiếm thiết bị Android đang cắm cáp.

---

## 2. Cách Nhập Danh Sách Email Đăng Ký (List Mail)

Danh sách tài khoản cần đăng ký được lưu trữ dưới dạng bảng Excel.

1. Tìm file danh sách tài khoản tại đường dẫn:
   `RegisterBot_Package/data/accounts.xlsx`
2. Điền thông tin vào 3 cột chính trong file Excel này:
   - **name**: Tên đăng ký (nếu để trống, hệ thống sẽ tự động sinh tên tiếng Nhật ngẫu nhiên).
   - **email**: Địa chỉ email đăng ký (Ví dụ: `mailgoc+may03@gmail.com`).
   - **password**: Mật khẩu mong muốn cho tài khoản.
3. Lưu file lại trước khi bấm chạy trên giao diện.

---

## 3. Cách Cấu Hình Gmail Master Để Nhận OTP

Để quét mã OTP tự động qua giao thức IMAP, bạn cần cung cấp thông tin tài khoản Gmail chủ (Master Mail) của mình.

### Bước 1: Tạo mật khẩu ứng dụng (App Password) trên Gmail
Vì các cơ chế bảo mật của Google không cho phép đăng nhập bằng mật khẩu thông thường qua các tập lệnh tự động, bạn **bắt buộc** phải tạo Mật khẩu ứng dụng (16 ký tự):
1. Truy cập trang quản lý tài khoản Google của bạn: [Tài khoản Google của tôi](https://myaccount.google.com/).
2. Vào mục **Bảo mật (Security)**.
3. Tìm phần **Mật khẩu ứng dụng (App passwords)** (Nếu không thấy, hãy bật tính năng Xác minh 2 bước trước).
4. Tạo một ứng dụng mới (Ví dụ chọn "Khác" và đặt tên là "Phone Bot"), Google sẽ cấp một mật khẩu gồm 16 ký tự viết liền (dạng `xxxx xxxx xxxx xxxx`).

### Bước 2: Cấu hình thông tin vào file cấu hình
Mở file [config.py](file:///c:/Users/Admin/Downloads/Amazon-tool/GDP-ToolAma-main/RegisterBot_Package/src/config.py) và cập nhật các thông số Gmail chủ:
```python
    # ── Gmail IMAP ──────────────────────────────────────────────────────────
    # Dùng Gmail App Password (16 ký tự), KHÔNG phải password Gmail thật.
    "gmail_address": "mailgoc@gmail.com",         # Gmail gốc của bạn
    "gmail_app_password": "xxxx xxxx xxxx xxxx",  # Mật khẩu ứng dụng 16 ký tự vừa tạo
    "imap_server": "imap.gmail.com",             # Giữ nguyên nếu dùng Gmail
```

---

## 4. Quy Trình Vận Hành Đăng Ký Thực Tế

1. **Kết nối điện thoại:** Kết nối các máy Android qua cáp USB vào máy tính (Đảm bảo đã bật tùy chọn **Gỡ lỗi USB - USB Debugging** trong cài đặt nhà phát triển).
2. **Khởi chạy ứng dụng:** Mở ứng dụng PyQt như hướng dẫn ở Mục 1.
3. **Quét thiết bị:** Click nút **🔄 Quét Thiết Bị USB** trên Sidebar để tool tìm kiếm và tự động stream màn hình các máy đang kết nối.
4. **Chọn thiết bị:** Click chọn (tích xanh) các thiết bị trong grid màn hình mà bạn muốn chạy đăng ký.
5. **Bắt đầu chạy:** Click nút **🚀 Bắt đầu Tạo tài khoản** trên Sidebar.
6. **Theo dõi:** 
   - Tool sẽ tự động phân phối tài khoản từ file `accounts.xlsx` vào các máy.
   - Diễn biến chi tiết (Clear cache, Mở Firefox, Gõ URL, Nhập email, Chờ OTP từ Gmail chủ, Gõ OTP và xác nhận) của từng máy sẽ được in trực tiếp lên khung log **TRẠNG THÁI HỆ THỐNG** trên Sidebar.
7. **Kết quả:** Sau khi chạy xong, kết quả đăng ký sẽ tự động được ghi nhận và xuất ra file `RegisterBot_Package/data/results.xlsx`.
