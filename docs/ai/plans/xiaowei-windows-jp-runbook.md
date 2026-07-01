# XiaoWei Windows JP Runbook

## Mục tiêu

Runbook này dùng khi bắt đầu test thực tế trên máy Windows bên Nhật đã:

- cài phần mềm XiaoWei
- cắm BoxPhone
- nhìn thấy thiết bị online trong XiaoWei

Mục tiêu test:

1. Xác nhận `RegisterBot` kết nối được tới XiaoWei API
2. Xác nhận bot nhìn thấy đúng danh sách BoxPhone
3. Chạy diagnostics smoke test ngay trong `RegisterBot`
4. Xác nhận các thao tác cốt lõi hoạt động
4. Chạy end-to-end 1 account

## Chuẩn bị trước khi test

- [ ] Máy Windows Nhật đang mở XiaoWei
- [ ] BoxPhone đã cắm và online trong XiaoWei
- [ ] Biết URL/port API thật của XiaoWei
- [ ] Có 1 account test dùng riêng
- [ ] Có product URL test
- [ ] Có Gmail OTP hoạt động
- [ ] Có quyền chụp log/screenshot để gửi lại

## File cần dùng

- Plan tổng: [xiaowei-direct-integration-plan.md](/Volumes/NghiemAnh%20Data/SourceCode/ama-tool/docs/ai/plans/xiaowei-direct-integration-plan.md)
- Config mẫu sạch: [config.xiaowei.example.json](/Volumes/NghiemAnh%20Data/SourceCode/ama-tool/RegisterBot_Package/data/config.xiaowei.example.json)

## Bước 1 - Chuẩn bị config

Mở config runtime của `RegisterBot` và chỉnh phần `xiaowei` theo mẫu.

Giá trị mục tiêu:

```json
{
  "xiaowei": {
    "enable": true,
    "api_type": "xiaowei",
    "api_url": "http://REPLACE_WITH_REAL_XIAOWEI_HOST:PORT",
    "devices": "all",
    "otp_source": "gmail",
    "screenshot_dir": "data/screenshots",
    "tap_delay": [0.5, 1.5]
  }
}
```

Checklist:

- [ ] `enable = true`
- [ ] `api_type = "xiaowei"`
- [ ] `api_url` đúng URL/port thật
- [ ] `devices = "all"` cho vòng test đầu
- [ ] `otp_source = "gmail"`

## Bước 2 - Mở dashboard và kiểm tra kết nối

Trong dashboard:

1. Mở phần cấu hình XiaoWei
2. Nhập `api_url`
3. Chọn `api_type = xiaowei`
4. Bấm `Kiểm Tra`

Kỳ vọng:

- hiện toast kết nối thành công
- panel device xuất hiện
- danh sách BoxPhone hiện ra

Checklist:

- [ ] Bấm `Kiểm Tra` không báo lỗi kết nối
- [ ] Danh sách device hiện ra
- [ ] Serial hiển thị đúng
- [ ] Model hiển thị hợp lý

Nếu fail:

- [ ] Ghi lại thông báo lỗi nguyên văn
- [ ] Chụp screenshot dashboard
- [ ] Ghi URL/port đã dùng

## Bước 3 - Smoke test thao tác cơ bản

Chọn 1 device test.

Mục tiêu:

- bot gọi được action cơ bản tới XiaoWei
- không cần chạy full flow ngay

Checklist:

- [ ] Chụp screenshot qua dashboard/API được
- [ ] Mở app/browser được
- [ ] Mở URL sản phẩm được
- [ ] Tap/click phản hồi đúng
- [ ] Có thể scroll

Evidence cần giữ:

- [ ] 1 screenshot file lưu về `data/screenshots`
- [ ] 1 ảnh chụp màn hình dashboard
- [ ] 1 log nếu thao tác fail

## Bước 3B - Chạy diagnostics tích hợp trong RegisterBot

Đã có sẵn 2 cách:

### Cách 1 - Từ web UI

- [ ] Bấm nút `Chẩn Đoán`
- [ ] Chờ panel kết quả hiện ra
- [ ] Kiểm tra report path được sinh ra trong `data/diagnostics`

Diagnostics hiện tại sẽ test:

- [ ] `get_devices`
- [ ] chọn 1 device để kiểm tra
- [ ] `adb wm size`
- [ ] `pm list packages com.android.chrome`
- [ ] screenshot
- [ ] `uiautomator dump`
- [ ] probe text đơn giản trong XML

### Cách 2 - Từ CLI

Chạy:

```bash
python main.py --diagnose-xiaowei
```

Hoặc chỉ định device:

```bash
python main.py --diagnose-xiaowei --device SERIAL_THAT
```

Checklist:

- [ ] Diagnostics chạy xong không crash
- [ ] Có report JSON được in ra hoặc lưu file
- [ ] `overall_success` đúng với thực tế
- [ ] Có `report_path`

## Bước 4 - Test `uiautomator dump`

Đây là bước quan trọng nhất.

Nếu bước này không ổn, chưa nên đi tiếp migration chính thức.

Checklist:

- [ ] Chạy được `uiautomator dump /sdcard/ui.xml`
- [ ] Đọc được `cat /sdcard/ui.xml`
- [ ] XML trả về không rỗng
- [ ] XML có text/element hợp lệ

Kết luận:

- [ ] PASS: XML ổn định
- [ ] FAIL: XML lỗi hoặc trống

## Bước 5 - End-to-end 1 account

Chạy 1 account test duy nhất.

Checklist:

- [ ] Bot nhận device từ XiaoWei
- [ ] Mở đúng trang sản phẩm
- [ ] Đi qua bước nhập email
- [ ] Đi qua bước tạo account
- [ ] Đi qua bước nhập password
- [ ] Lấy OTP Gmail thành công
- [ ] Nhập OTP thành công
- [ ] Có kết quả cuối trong dashboard
- [ ] Có record trong file kết quả

Evidence:

- [ ] Screenshot các bước chính
- [ ] Log chạy bot
- [ ] File `results.xlsx`

## Bước 6 - Ghi nhận kết quả về plan tổng

Sau khi test xong:

- [ ] Mở plan tổng
- [ ] Tick các mục đã pass
- [ ] Ghi chú mục nào fail
- [ ] Ghi lại URL/port XiaoWei thật
- [ ] Ghi lại serial device đã test

## Mẫu báo cáo ngắn sau mỗi vòng test

```txt
Ngày test:
Máy:
URL XiaoWei:
Device serial:

Kết quả:
- Kết nối dashboard: PASS/FAIL
- List device: PASS/FAIL
- Screenshot: PASS/FAIL
- uiautomator dump: PASS/FAIL
- End-to-end 1 account: PASS/FAIL

Lỗi chính:
- ...

Ghi chú:
- ...
```
